from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db.enums import ProviderEnum
from repositories.account import AccountRepository
from repositories.user import UserRepository
from telegram.keyboards import main_menu_keyboard, manage_rooms_keyboard
from telegram.states import RegistrationStates

router = Router()
user_repo = UserRepository()
account_repo = AccountRepository()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    account = await account_repo.get_by_chat_id(message.from_user.id)

    if account:
        user_has_active_room = await user_repo.has_active_room(account.user.id)
        await message.answer(
            "Hey! 👋",
            reply_markup=(
                manage_rooms_keyboard(has_active_room=user_has_active_room)
                if not user_has_active_room
                else main_menu_keyboard(is_superuser=account.user.is_superuser)
            ),
        )
        return

    await message.answer("👋 Welcome! Let's get you registered.\n\nWhat's your name?")
    await state.set_state(RegistrationStates.name)


@router.message(RegistrationStates.name)
async def handle_name(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Please enter a valid name.")
        return

    name = message.text.strip()

    if not name or len(name) < 2:
        await message.answer("Please enter a valid name (at least 2 characters).")
        return

    try:
        user = await user_repo.register_user(
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
