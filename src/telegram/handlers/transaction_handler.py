from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db.models import Category
from repositories import (
    AccountRepository,
    CategoryRepository,
    TransactionRepository,
    UserRepository,
)
from schemas import TransactionDraft
from services import build_transaction_draft
from telegram.helpers import _format_draft_summary, get_first_stage
from telegram.keyboards import transaction_confirmation_keyboard
from telegram.states import TransactionStates

router = Router()
# One in-flight parse per Telegram user. aiogram polls with handle_as_tasks=True,
# so two expense messages in the same getUpdates batch both match StateFilter(None)
# and would otherwise overwrite FSM `draft` — Confirm then saves the wrong expense.
_drafting_users: set[int] = set()
_ALREADY_PROCESSING_MESSAGE = "⏳ Already processing a transaction. Please wait."


@router.message(F.text == "📝 Add Transaction")
async def prompt_transaction(message: Message) -> None:
    await message.answer(
        "Describe the transaction in natural language.\n\n"
        "Example: I paid 50000 tomans for groceries, split equally with Ali and Sara."
    )


@router.message(StateFilter(None), F.text)
async def handle_transaction_draft(message: Message, state: FSMContext) -> None:
    account = await AccountRepository().get_by_chat_id(message.from_user.id)
    if not account:
        return

    if not await UserRepository().has_active_room(account.user_id):
        await message.answer("You need an active room before adding transactions.")
        return

    user_id = message.from_user.id
    if user_id in _drafting_users:
        await message.answer(_ALREADY_PROCESSING_MESSAGE)
        return
    _drafting_users.add(user_id)

    try:
        processing_msg = await message.answer("⏳ Processing...")

        try:
            draft, users_map = await build_transaction_draft(
                message=message.text,  # type: ignore
                created_by_id=account.user_id,
            )
        except Exception:
            await processing_msg.edit_text(
                "❌ Could not parse the transaction. Please try again with a clearer message."
            )
            return

        category_name = None
        if draft.category_id:
            category_name = await CategoryRepository().find(
                filters=[Category.id == draft.category_id],
                columns=[Category.name],
            )

        summary = _format_draft_summary(draft, users_map, category_name=category_name)

        await state.update_data(draft=draft.model_dump(), users_map=users_map)
        await state.set_state(TransactionStates.confirming)
        await processing_msg.edit_text(summary, reply_markup=transaction_confirmation_keyboard())
    finally:
        _drafting_users.discard(user_id)


@router.callback_query(F.data == "transaction:confirm", StateFilter(TransactionStates.confirming))
async def handle_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = TransactionDraft.model_validate(data["draft"])

    await TransactionRepository().create(draft)
    await state.clear()

    await callback.answer("Transaction saved!")
    await callback.message.edit_text("✅ Transaction saved successfully.")

    text, keyboard = await get_first_stage(chat_id=callback.from_user.id)
    await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "transaction:cancel", StateFilter(TransactionStates.confirming))
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()

    await callback.answer("Cancelled")
    await callback.message.edit_text("❌ Transaction cancelled.")

    text, keyboard = await get_first_stage(chat_id=callback.from_user.id)
    await callback.message.answer(text, reply_markup=keyboard)
