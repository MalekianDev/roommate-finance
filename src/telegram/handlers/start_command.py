from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db.enums import ProviderEnum
from repositories import UserRepository, AccountRepository
from telegram.keyboards import main_menu_keyboard
from telegram.states import RegistrationStates
from telegram.helpers import get_first_stage

router = Router()
user_repo = UserRepository()
account_repo = AccountRepository()


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
