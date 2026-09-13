import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from telegram.handlers import room_handler
from telegram.handlers.room_handler import (
    handle_cancel_room,
    handle_confirm_room,
    handle_room_name,
    handle_wrong_type_room_name,
    manage_rooms_handler,
    room_creation_handler,
)
from telegram.states import RoomStates


@pytest.mark.asyncio
async def test_manage_rooms_handler_shows_keyboard(message, state):
    await manage_rooms_handler(message, state)

    assert message.answer.await_args.kwargs["reply_markup"].keyboard[0][0].text == "🤝 Create Room"


@pytest.mark.asyncio
async def test_room_creation_handler_asks_for_name(message, state):
    await room_creation_handler(message, state)

    assert "enter room name" in message.answer.await_args.args[0]
    state.set_state.assert_awaited_once_with(RoomStates.name)


@pytest.mark.asyncio
async def test_wrong_type_room_name_prompts_again(message, state):
    await handle_wrong_type_room_name(message, state)

    message.answer.assert_awaited_once_with("Please enter a valid room name.")


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", " ", "A"])
async def test_handle_room_name_rejects_short_names(message, state, text):
    message.text = text

    await handle_room_name(message, state)

    message.answer.assert_awaited_once_with("Please enter a valid room name (at least 2 characters).")
    state.update_data.assert_not_called()


@pytest.mark.asyncio
async def test_handle_room_name_stores_name_and_asks_for_confirmation(message, state):
    message.text = "  Flat  "

    await handle_room_name(message, state)

    state.update_data.assert_awaited_once_with(room_name="Flat")
    state.set_state.assert_awaited_once_with(RoomStates.confirming)
    assert "Are you sure" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_handle_confirm_room_registers_room_and_sends_invite(monkeypatch, message, state, account):
    state.get_data = AsyncMock(return_value={"room_name": "Flat"})
    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=account)
    room_repo = MagicMock()
    room_repo.register_room = AsyncMock(
        return_value=SimpleNamespace(name="Flat", invite_token="token-1"),
    )
    monkeypatch.setattr("telegram.handlers.room_handler.AccountRepository", lambda: account_repo)
    monkeypatch.setattr("telegram.handlers.room_handler.RoomRepository", lambda: room_repo)
    monkeypatch.setattr(
        "telegram.handlers.room_handler.create_start_link",
        AsyncMock(return_value="https://t.me/bot?start=invite"),
    )
    monkeypatch.setattr(
        "telegram.handlers.room_handler.get_first_stage",
        AsyncMock(return_value=("invite text", MagicMock())),
    )
    bot = MagicMock()

    await handle_confirm_room(message, state, bot)

    room_repo.register_room.assert_awaited_once_with(name="Flat", created_by=account.user)
    state.update_data.assert_awaited_once_with(room_name=None)
    message.answer.assert_awaited_once()
    assert message.answer.await_args.kwargs["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_handle_confirm_room_skips_when_draft_already_consumed(monkeypatch, message, state):
    state.get_data = AsyncMock(return_value={})
    room_repo = MagicMock()
    room_repo.register_room = AsyncMock()
    monkeypatch.setattr("telegram.handlers.room_handler.RoomRepository", lambda: room_repo)

    await handle_confirm_room(message, state, MagicMock())

    room_repo.register_room.assert_not_called()
    message.answer.assert_awaited_once_with("Room creation was already processed.")


@pytest.mark.asyncio
async def test_handle_confirm_room_does_not_create_two_rooms_on_double_yes(
    monkeypatch, message, state, account
):
    room_handler._creating_room_users.clear()
    state.get_data = AsyncMock(return_value={"room_name": "Flat"})
    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=account)
    started = asyncio.Event()
    release = asyncio.Event()
    register_calls: list[str] = []

    async def slow_register(*, name, created_by):
        register_calls.append(name)
        started.set()
        await release.wait()
        return SimpleNamespace(name=name, invite_token="token-1")

    monkeypatch.setattr("telegram.handlers.room_handler.AccountRepository", lambda: account_repo)
    monkeypatch.setattr(
        "telegram.handlers.room_handler.RoomRepository",
        lambda: SimpleNamespace(register_room=slow_register),
    )
    monkeypatch.setattr(
        "telegram.handlers.room_handler.create_start_link",
        AsyncMock(return_value="https://t.me/bot?start=invite"),
    )
    monkeypatch.setattr(
        "telegram.handlers.room_handler.get_first_stage",
        AsyncMock(return_value=("invite text", MagicMock())),
    )

    first = asyncio.create_task(handle_confirm_room(message, state, MagicMock()))
    await started.wait()
    await handle_confirm_room(message, state, MagicMock())
    release.set()
    await first

    assert register_calls == ["Flat"]
    answers = [call.args[0] for call in message.answer.await_args_list if call.args]
    assert "Room is already being created." in answers


@pytest.mark.asyncio
async def test_handle_cancel_room_returns_to_first_stage(monkeypatch, message, state):
    monkeypatch.setattr(
        "telegram.handlers.room_handler.get_first_stage",
        AsyncMock(return_value=("Room creation canceled.", MagicMock())),
    )

    await handle_cancel_room(message, state)

    message.answer.assert_awaited_once()
    assert message.answer.await_args.args[0] == "Room creation canceled."
