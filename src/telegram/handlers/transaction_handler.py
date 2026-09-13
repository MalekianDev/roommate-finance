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
_saving_transaction_users: set[int] = set()


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

    processing_msg = await message.answer("⏳ Processing...")

    try:
        draft, users_map = await build_transaction_draft(
            message=message.text, # type: ignore
            created_by_id=account.user_id,
        )
    except Exception:
        await processing_msg.edit_text("❌ Could not parse the transaction. Please try again with a clearer message.")
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


@router.callback_query(F.data == "transaction:confirm", StateFilter(TransactionStates.confirming))
async def handle_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    if user_id in _saving_transaction_users:
        await callback.answer("Transaction is already being saved.")
        return

    _saving_transaction_users.add(user_id)
    try:
        data = await state.get_data()
        draft_data = data.get("draft")
        if not draft_data:
            await callback.answer("This transaction was already processed.")
            return

        await state.update_data(draft=None)
        draft = TransactionDraft.model_validate(draft_data)

        try:
            await TransactionRepository().create(draft)
        except ValueError:
            await state.clear()
            await callback.answer("Could not save this transaction.", show_alert=True)
            await callback.message.edit_text("❌ Could not save this transaction. Please describe it again.")
            return

        await state.clear()
        await callback.answer("Transaction saved!")
        await callback.message.edit_text("✅ Transaction saved successfully.")

        text, keyboard = await get_first_stage(chat_id=callback.from_user.id)
        await callback.message.answer(text, reply_markup=keyboard)
    finally:
        _saving_transaction_users.discard(user_id)


@router.callback_query(F.data == "transaction:cancel", StateFilter(TransactionStates.confirming))
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()

    await callback.answer("Cancelled")
    await callback.message.edit_text("❌ Transaction cancelled.")

    text, keyboard = await get_first_stage(chat_id=callback.from_user.id)
    await callback.message.answer(text, reply_markup=keyboard)
