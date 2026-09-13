from decimal import Decimal

from sqlalchemy import select

from db.models import Payment, RoomMember, Split, Transaction
from repositories.base import BaseRepository
from schemas.transaction import Transaction as TransactionDraft


class TransactionRepository(BaseRepository[Transaction]):
    """
    Repository for transaction-related operations.
    """

    model = Transaction

    async def create(self, obj: TransactionDraft) -> Transaction:
        await self._validate_draft(obj)

        transaction = Transaction(
            category_id=obj.category_id,
            room_id=obj.room_id,
            description=obj.description,
            created_by_id=obj.created_by_id,
        )
        self.session.add(transaction)
        await self.session.flush()

        for payment in obj.payments:
            self.session.add(
                Payment(
                    amount=Decimal(str(payment.amount)),
                    transaction_id=transaction.id,
                    paid_by_id=payment.user_id,
                    created_by_id=obj.created_by_id,
                )
            )

        for split in obj.splits:
            self.session.add(
                Split(
                    amount=Decimal(str(split.amount)),
                    transaction_id=transaction.id,
                    owed_by_id=split.user_id,
                    created_by_id=obj.created_by_id,
                )
            )

        await self.session.commit()
        await self.session.refresh(transaction)

        return transaction

    async def _validate_draft(self, obj: TransactionDraft) -> None:
        if obj.room_id is None:
            raise ValueError("A transaction must belong to a room.")
        if not obj.payments or not obj.splits:
            raise ValueError("A transaction must include payments and splits.")

        result = await self.session.scalars(select(RoomMember.user_id).where(RoomMember.room_id == obj.room_id))
        member_ids = set(result.all())

        if obj.created_by_id not in member_ids:
            raise ValueError("Creator is not a member of the selected room.")

        payment_ids = {payment.user_id for payment in obj.payments}
        split_ids = {split.user_id for split in obj.splits}
        if not payment_ids <= member_ids or not split_ids <= member_ids:
            raise ValueError("Payments and splits must use members of the selected room.")
