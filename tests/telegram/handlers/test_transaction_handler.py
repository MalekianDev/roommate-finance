import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from telegram.handlers.transaction_handler import (
    _ALREADY_PROCESSING_MESSAGE,
    handle_cancel,
    handle_confirm,
    handle_transaction_draft,
    prompt_transaction,
)
from telegram.states import TransactionStates


@pytest.mark.asyncio
async def test_prompt_transaction_asks_for_a_description(message):
    await prompt_transaction(message)

    message.answer.assert_awaited_once()
    assert "Describe the transaction" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_handle_transaction_draft_ignores_unknown_accounts(monkeypatch, message, state):
    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=None)
    monkeypatch.setattr("telegram.handlers.transaction_handler.AccountRepository", lambda: account_repo)

    await handle_transaction_draft(message, state)

    message.answer.assert_not_called()
    state.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_handle_transaction_draft_requires_an_active_room(monkeypatch, message, state, account):
    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=account)
    user_repo = MagicMock()
    user_repo.has_active_room = AsyncMock(return_value=False)
    monkeypatch.setattr("telegram.handlers.transaction_handler.AccountRepository", lambda: account_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.UserRepository", lambda: user_repo)

    await handle_transaction_draft(message, state)

    message.answer.assert_awaited_once_with("You need an active room before adding transactions.")
    state.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_handle_transaction_draft_reports_parse_failures(monkeypatch, message, state, account):
    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)
    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=account)
    user_repo = MagicMock()
    user_repo.has_active_room = AsyncMock(return_value=True)
    monkeypatch.setattr("telegram.handlers.transaction_handler.AccountRepository", lambda: account_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.UserRepository", lambda: user_repo)
    monkeypatch.setattr(
        "telegram.handlers.transaction_handler.build_transaction_draft",
        AsyncMock(side_effect=ValueError("bad json")),
    )

    await handle_transaction_draft(message, state)

    processing_msg.edit_text.assert_awaited_once()
    assert "Could not parse" in processing_msg.edit_text.await_args.args[0]
    state.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_handle_transaction_draft_stores_preview_on_success(
    monkeypatch,
    message,
    state,
    account,
    transaction_draft,
    users_map,
):
    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)
    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=account)
    user_repo = MagicMock()
    user_repo.has_active_room = AsyncMock(return_value=True)
    category_repo = MagicMock()
    category_repo.find = AsyncMock(return_value="Food")
    monkeypatch.setattr("telegram.handlers.transaction_handler.AccountRepository", lambda: account_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.UserRepository", lambda: user_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.CategoryRepository", lambda: category_repo)
    monkeypatch.setattr(
        "telegram.handlers.transaction_handler.build_transaction_draft",
        AsyncMock(return_value=(transaction_draft, users_map)),
    )

    await handle_transaction_draft(message, state)

    state.update_data.assert_awaited_once_with(draft=transaction_draft.model_dump(), users_map=users_map)
    state.set_state.assert_awaited_once_with(TransactionStates.confirming)
    summary = processing_msg.edit_text.await_args.args[0]
    assert "Dinner" in summary
    assert "Food" in summary
    assert processing_msg.edit_text.await_args.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == (
        "transaction:confirm"
    )


@pytest.mark.asyncio
async def test_handle_transaction_draft_rejects_concurrent_parse_for_same_user(
    monkeypatch,
    message,
    state,
    account,
    transaction_draft,
    users_map,
):
    """Two in-flight parses used to share one FSM draft; Confirm saved the wrong expense."""
    started = asyncio.Event()
    release = asyncio.Event()
    build_calls = 0

    async def slow_build(**kwargs):
        nonlocal build_calls
        build_calls += 1
        started.set()
        await release.wait()
        return transaction_draft, users_map

    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)
    second_message = MagicMock()
    second_message.text = "I paid 100 for rent"
    second_message.from_user = SimpleNamespace(id=message.from_user.id)
    second_message.answer = AsyncMock()

    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=account)
    user_repo = MagicMock()
    user_repo.has_active_room = AsyncMock(return_value=True)
    category_repo = MagicMock()
    category_repo.find = AsyncMock(return_value="Food")
    monkeypatch.setattr("telegram.handlers.transaction_handler.AccountRepository", lambda: account_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.UserRepository", lambda: user_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.CategoryRepository", lambda: category_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.build_transaction_draft", slow_build)

    first = asyncio.create_task(handle_transaction_draft(message, state))
    await started.wait()

    await handle_transaction_draft(second_message, state)

    second_message.answer.assert_awaited_once_with(_ALREADY_PROCESSING_MESSAGE)
    assert build_calls == 1
    state.set_state.assert_not_called()

    release.set()
    await first

    state.set_state.assert_awaited_once_with(TransactionStates.confirming)
    state.update_data.assert_awaited_once_with(draft=transaction_draft.model_dump(), users_map=users_map)
    assert build_calls == 1


@pytest.mark.asyncio
async def test_handle_transaction_draft_releases_lock_after_parse_failure(
    monkeypatch,
    message,
    state,
    account,
    transaction_draft,
    users_map,
):
    processing_msg = MagicMock()
    processing_msg.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=processing_msg)
    account_repo = MagicMock()
    account_repo.get_by_chat_id = AsyncMock(return_value=account)
    user_repo = MagicMock()
    user_repo.has_active_room = AsyncMock(return_value=True)
    category_repo = MagicMock()
    category_repo.find = AsyncMock(return_value="Food")
    monkeypatch.setattr("telegram.handlers.transaction_handler.AccountRepository", lambda: account_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.UserRepository", lambda: user_repo)
    monkeypatch.setattr("telegram.handlers.transaction_handler.CategoryRepository", lambda: category_repo)

    builds = AsyncMock(side_effect=[ValueError("bad json"), (transaction_draft, users_map)])
    monkeypatch.setattr("telegram.handlers.transaction_handler.build_transaction_draft", builds)

    await handle_transaction_draft(message, state)
    await handle_transaction_draft(message, state)

    assert builds.await_count == 2
    state.set_state.assert_awaited_once_with(TransactionStates.confirming)


@pytest.mark.asyncio
async def test_handle_confirm_saves_draft_and_clears_state(
    monkeypatch,
    callback,
    state,
    transaction_draft,
):
    state.get_data = AsyncMock(return_value={"draft": transaction_draft.model_dump()})
    transaction_repo = MagicMock()
    transaction_repo.create = AsyncMock()
    monkeypatch.setattr("telegram.handlers.transaction_handler.TransactionRepository", lambda: transaction_repo)
    monkeypatch.setattr(
        "telegram.handlers.transaction_handler.get_first_stage",
        AsyncMock(return_value=("Main menu:", MagicMock())),
    )

    await handle_confirm(callback, state)

    transaction_repo.create.assert_awaited_once()
    saved_draft = transaction_repo.create.await_args.args[0]
    assert saved_draft.description == "Dinner"
    state.clear.assert_awaited_once()
    callback.answer.assert_awaited_once_with("Transaction saved!")
    callback.message.edit_text.assert_awaited_once_with("✅ Transaction saved successfully.")
    callback.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_cancel_clears_state_without_saving(monkeypatch, callback, state):
    transaction_repo = MagicMock()
    transaction_repo.create = AsyncMock()
    monkeypatch.setattr("telegram.handlers.transaction_handler.TransactionRepository", lambda: transaction_repo)
    monkeypatch.setattr(
        "telegram.handlers.transaction_handler.get_first_stage",
        AsyncMock(return_value=("Main menu:", MagicMock())),
    )

    await handle_cancel(callback, state)

    transaction_repo.create.assert_not_called()
    state.clear.assert_awaited_once()
    callback.answer.assert_awaited_once_with("Cancelled")
    callback.message.edit_text.assert_awaited_once_with("❌ Transaction cancelled.")
