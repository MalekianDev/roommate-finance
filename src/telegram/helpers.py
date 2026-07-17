from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup

from repositories import UserRepository, AccountRepository
from telegram.states import RegistrationStates
from telegram.keyboards import main_menu_keyboard, manage_rooms_keyboard


async def get_first_stage(
    chat_id: int,
    state: FSMContext | None = None,
    custom_text: str | None = None,
) -> tuple[str, ReplyKeyboardMarkup]:
    """
    Get the first stage of the conversation.

    If the user is not registered, return the registration state.
    If the user has an active room, return the main menu.
    If not has an active room, return the manage rooms keyboard.
    If user is registered and state is not None, clear the state.

    args:
        chat_id: The chat ID.
        state: The FSM context.
        custom_text: The custom text to show to the user.

    Return:
        tuple[str, ReplyKeyboardMarkup]: The text and keyboard to show to the user.
    """
    account_repo = AccountRepository()
    account = await account_repo.get_by_chat_id(chat_id)

    if account:
        user_repo = UserRepository()
        user_has_active_room = await user_repo.has_active_room(account.user_id)

        if user_has_active_room:
            text, keyboard = custom_text or "Main menu:", main_menu_keyboard(is_superuser=account.is_superuser)
        else:
            text, keyboard = custom_text or "You need an active room:", manage_rooms_keyboard(has_active_room=False)

        if state:
            await state.clear()
    else:
        text, keyboard = custom_text or "👋 Welcome! Let's get you registered.\n\nWhat's your name?"
        await state.set_state(RegistrationStates.name)

    return text, keyboard
