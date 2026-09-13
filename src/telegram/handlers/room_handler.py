from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.deep_linking import create_start_link

from repositories import AccountRepository, RoomRepository
from telegram.helpers import get_first_stage
from telegram.keyboards import BACK_KEYBOARD, YES_NO_KEYBOARD, manage_rooms_keyboard
from telegram.states import RoomStates

router = Router()
_creating_room_users: set[int] = set()


@router.message(F.text == "👯 Manage Rooms")
async def manage_rooms_handler(message: Message, state: FSMContext) -> None:
    await message.answer("Manage rooms:", reply_markup=manage_rooms_keyboard(has_active_room=True))


@router.message(F.text == "🤝 Create Room")
async def room_creation_handler(message: Message, state: FSMContext) -> None:
    await message.answer("Please, enter room name:", reply_markup=BACK_KEYBOARD)
    await state.set_state(RoomStates.name)


@router.message(RoomStates.name, ~F.text)
async def handle_wrong_type_room_name(message: Message, state: FSMContext) -> None:
    await message.answer("Please enter a valid room name.")


@router.message(RoomStates.name, F.text)
async def handle_room_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or len(name) < 2:
        await message.answer("Please enter a valid room name (at least 2 characters).")
        return

    await state.update_data(room_name=name)
    await message.answer(
        "✅ Room name set.\n\nAre you sure you want to create this room?",
        reply_markup=YES_NO_KEYBOARD,
    )
    await state.set_state(RoomStates.confirming)


@router.message(RoomStates.confirming, F.text == "✅ Yes")
async def handle_confirm_room(message: Message, state: FSMContext, bot: Bot) -> None:
    user_id = message.from_user.id
    if user_id in _creating_room_users:
        await message.answer("Room is already being created.")
        return

    _creating_room_users.add(user_id)
    try:
        data = await state.get_data()
        room_name = data.get("room_name")
        if not room_name:
            await message.answer("Room creation was already processed.")
            return

        # Drop the draft before the Telegram round-trip so a second Yes cannot persist another room.
        await state.update_data(room_name=None)

        account = await AccountRepository().get_by_chat_id(chat_id=message.from_user.id)
        room = await RoomRepository().register_room(name=room_name, created_by=account.user)

        text, keyboard = await get_first_stage(
            chat_id=message.from_user.id,
            state=state,
            account=account,
            custom_text=f"✅ Room <code>{room.name}</code> created.\n\nNow you should send this URL to your roommates:\n\n"
            f"<a href='{await create_start_link(bot, room.invite_token, encode=True)}'>INVITE LINK</a>",
        )
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    finally:
        _creating_room_users.discard(user_id)


@router.message(RoomStates.confirming, F.text == "❌ No")
async def handle_cancel_room(message: Message, state: FSMContext) -> None:
    text, keyboard = await get_first_stage(
        chat_id=message.from_user.id, state=state, custom_text="Room creation canceled."
    )
    await message.answer(text, reply_markup=keyboard)
