import uuid

from aiogram import Router, F
from aiogram.utils.deep_linking import decode_payload
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db.enums import ProviderEnum
from db.models import Account, Room, RoomMember
from repositories import UserRepository, AccountRepository, RoomRepository, RoomMemberRepository
from telegram.keyboards import main_menu_keyboard
from telegram.states import RegistrationStates
from telegram.helpers import get_first_stage

router = Router()


@router.message(CommandStart(deep_link=True))
async def handle_join_start(message: Message, command: CommandObject) -> None:
    room_member_repo = RoomMemberRepository()

    room_id = await RoomRepository().find(
        filters=[Room.invite_token == uuid.UUID(decode_payload(command.args)).hex], columns=[Room.id]
    )

    if not room_id:
        await message.answer("Invalid invite token.")
        return

    user_id = await AccountRepository().find(
        filters=[Account.uid == str(message.from_user.id), Account.provider == ProviderEnum.TELEGRAM],
        columns=[Account.user_id],
    )
    room_member = await room_member_repo.find(
        filters=[RoomMember.room_id == room_id, RoomMember.user_id == user_id], columns=[RoomMember.id]
    )

    if room_member:
        await message.answer("You are already in this room.")
        return

    # TODO -> Add a "JoinRequest" concept to handle room requests instead of directly adding to the room.
    await room_member_repo.create(RoomMember(room_id=room_id, user_id=user_id))
    await message.answer("✅ You have joined the room.")


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    text, keybaord = await get_first_stage(chat_id=message.from_user.id, state=state, custom_text="👋 Hey")
    await message.reply(text, reply_markup=keybaord)


@router.message(RegistrationStates.name, ~F.text)
async def handle_wrong_type_name(message: Message, state: FSMContext) -> None:
    await message.answer("Please enter a valid name.")


@router.message(RegistrationStates.name, F.text)
async def handle_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or len(name) < 2:
        await message.answer("Please enter a valid name (at least 2 characters).")
        return

    try:
        user = await UserRepository().register_user(
            name=name,
            username=str(message.from_user.id),
            provider=ProviderEnum.TELEGRAM,
            uid=str(message.from_user.id),
        )
        await state.clear()
        await message.answer(
            f"✅ Welcome, {user.name}!\n\n"
            f"{'You are registered as superuser.' if user.is_superuser else 'You are registered.'}",
            reply_markup=main_menu_keyboard(is_superuser=user.is_superuser),
        )
    except ValueError as e:
        await message.answer(f"❌ Registration failed: {e}")
