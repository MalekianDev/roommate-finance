from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from db.context import DBContext
from db.enums import ProviderEnum
from db.models import Account, Payment, Room, RoomMember, Split, Transaction, User
from repositories.room import RoomRepository
from repositories.transaction import TransactionRepository
from repositories.user import UserRepository
from schemas.transaction import Payment as PaymentDraft
from schemas.transaction import Split as SplitDraft
from schemas.transaction import Transaction as TransactionDraft


@pytest.mark.asyncio
async def test_create_persists_toman_deposit_scale_amounts():
    """Amounts >= 10^8 used to overflow Numeric(10, 2) and crash on confirm."""
    async with DBContext():
        user_repo = UserRepository()
        suffix = uuid4().hex[:8]
        sam = await user_repo.register_user(
            name="Sam",
            username=f"amount_precision_sam_{suffix}",
            provider=ProviderEnum.TELEGRAM,
            uid=f"amount-precision-sam-{suffix}",
        )
        ali = User(name="Ali", username=f"amount_precision_ali_{suffix}")
        user_repo.session.add(ali)
        await user_repo.session.flush()

        room = await RoomRepository().register_room(name="Deposit Flat", created_by=sam)
        user_repo.session.add(RoomMember(room=room, user=ali))
        await user_repo.session.commit()

        draft = TransactionDraft(
            room_id=room.id,
            created_by_id=sam.id,
            description="Rahn deposit",
            total_amount=150_000_000,
            payments=[PaymentDraft(user_id=sam.id, amount=150_000_000)],
            splits=[
                SplitDraft(user_id=sam.id, amount=75_000_000),
                SplitDraft(user_id=ali.id, amount=75_000_000),
            ],
        )

        try:
            transaction = await TransactionRepository().create(draft)
            payment_amount = await user_repo.session.scalar(
                select(Payment.amount).where(Payment.transaction_id == transaction.id)
            )
            split_result = await user_repo.session.scalars(
                select(Split.amount).where(Split.transaction_id == transaction.id)
            )
            assert payment_amount == Decimal("150000000.00")
            assert set(split_result.all()) == {Decimal("75000000.00")}
        finally:
            session = user_repo.session
            await session.execute(delete(Payment).where(Payment.created_by_id.in_([sam.id, ali.id])))
            await session.execute(delete(Split).where(Split.created_by_id.in_([sam.id, ali.id])))
            await session.execute(delete(Transaction).where(Transaction.created_by_id.in_([sam.id, ali.id])))
            await session.execute(delete(RoomMember).where(RoomMember.user_id.in_([sam.id, ali.id])))
            await session.execute(delete(Room).where(Room.created_by_id == sam.id))
            await session.execute(delete(Account).where(Account.user_id.in_([sam.id, ali.id])))
            await session.execute(delete(User).where(User.id.in_([sam.id, ali.id])))
            await session.commit()
