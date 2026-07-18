from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from settings import Settings
from db.models import Room
from repositories import RoomRepository, AccountRepository

from telegram.states import RoomStates
from telegram.keyboards import BACK_KEYBOARD, YES_NO_KEYBOARD
from telegram.helpers import get_first_stage

router = Router()


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
async def handle_confirm_room(message: Message, state: FSMContext) -> None:
    settings = Settings()
    data = await state.get_data()

    account = await AccountRepository().get_by_chat_id(message.from_user.id)
    room = await RoomRepository().create(Room(name=data["room_name"], created_by=account.user))

    text, keyboard = await get_first_stage(
        chat_id=message.from_user.id,
        state=state,
        account=account,
        custom_text=f"✅ Room <code>{room.name}</code> created.\n\nNow you should send this URL to your roommates:\n\n"
        f"<a href='https://t.me/{settings.bot_username}?start={room.invite_token}'>INVITE LINK</a>",
    )
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(RoomStates.confirming, F.text == "❌ No")
async def handle_cancel_room(message: Message, state: FSMContext) -> None:
    text, keyboard = await get_first_stage(
        chat_id=message.from_user.id, state=state, custom_text="Room creation canceled."
    )
    await message.answer(text, reply_markup=keyboard)
