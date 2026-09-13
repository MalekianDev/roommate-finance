from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from db.models import Payment, Split, Transaction
from repositories.transaction import TransactionRepository


def _set_member_ids(session, user_ids):
    result = MagicMock()
    result.all.return_value = list(user_ids)
    session.scalars = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()


@pytest.mark.asyncio
async def test_create_maps_draft_into_transaction_payments_and_splits(session, transaction_draft):
    _set_member_ids(session, [7, 8])
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
async def test_create_rejects_draft_without_a_room(session, transaction_draft):
    transaction_draft.room_id = None
    _set_member_ids(session, [7, 8])

    with pytest.raises(ValueError, match="must belong to a room"):
        await TransactionRepository().create(transaction_draft)

    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_rejects_draft_without_splits(session, transaction_draft):
    transaction_draft.splits = []
    _set_member_ids(session, [7, 8])

    with pytest.raises(ValueError, match="payments and splits"):
        await TransactionRepository().create(transaction_draft)

    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_rejects_when_creator_is_not_a_room_member(session, transaction_draft):
    _set_member_ids(session, [8])

    with pytest.raises(ValueError, match="not a member"):
        await TransactionRepository().create(transaction_draft)

    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_rejects_splits_for_users_outside_the_room(session, transaction_draft):
    _set_member_ids(session, [7])

    with pytest.raises(ValueError, match="members of the selected room"):
        await TransactionRepository().create(transaction_draft)

    session.add.assert_not_called()
    session.commit.assert_not_called()
