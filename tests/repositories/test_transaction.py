from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from db.models import Payment, Split, Transaction
from repositories.transaction import TransactionRepository
from schemas.transaction import Payment as PaymentDraft
from schemas.transaction import Split as SplitDraft


def test_payment_and_split_columns_accept_toman_deposit_amounts():
    assert Transaction.__table__ is not None
    assert Payment.__table__.c.amount.type.precision == 15
    assert Payment.__table__.c.amount.type.scale == 2
    assert Split.__table__.c.amount.type.precision == 15
    assert Split.__table__.c.amount.type.scale == 2


@pytest.mark.asyncio
async def test_create_maps_draft_into_transaction_payments_and_splits(session, transaction_draft):
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    repo = TransactionRepository()

    result = await repo.create(transaction_draft)

    assert isinstance(result, Transaction)
    assert result.category_id == 1
    assert result.room_id == 10
    assert result.description == "Dinner"
    assert result.created_by_id == 7

    added = [call.args[0] for call in session.add.call_args_list]
    assert added[0] is result
    payments = [obj for obj in added if isinstance(obj, Payment)]
    splits = [obj for obj in added if isinstance(obj, Split)]
    assert len(payments) == 1
    assert payments[0].amount == Decimal("42.5")
    assert payments[0].paid_by_id == 7
    assert payments[0].created_by_id == 7
    assert {split.owed_by_id for split in splits} == {7, 8}
    assert {split.amount for split in splits} == {Decimal("21.25")}
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_create_skips_splits_when_draft_has_none(session, transaction_draft):
    transaction_draft.splits = []
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    await TransactionRepository().create(transaction_draft)

    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(obj, Payment) for obj in added)
    assert not any(isinstance(obj, Split) for obj in added)


@pytest.mark.asyncio
async def test_create_maps_amounts_larger_than_one_hundred_million(session, transaction_draft):
    transaction_draft.total_amount = 150_000_000
    transaction_draft.payments = [PaymentDraft(user_id=7, amount=150_000_000)]
    transaction_draft.splits = [
        SplitDraft(user_id=7, amount=75_000_000),
        SplitDraft(user_id=8, amount=75_000_000),
    ]
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    await TransactionRepository().create(transaction_draft)

    added = [call.args[0] for call in session.add.call_args_list]
    payments = [obj for obj in added if isinstance(obj, Payment)]
    splits = [obj for obj in added if isinstance(obj, Split)]
    assert payments[0].amount == Decimal("150000000")
    assert {split.amount for split in splits} == {Decimal("75000000")}


@pytest.mark.asyncio
async def test_create_rolls_back_when_commit_fails(session, transaction_draft):
    session.flush = AsyncMock()
    session.commit = AsyncMock(side_effect=RuntimeError("numeric field overflow"))
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()

    with pytest.raises(RuntimeError, match="numeric field overflow"):
        await TransactionRepository().create(transaction_draft)

    session.rollback.assert_awaited_once()
    session.refresh.assert_not_called()
