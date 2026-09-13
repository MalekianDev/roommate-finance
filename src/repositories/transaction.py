from decimal import Decimal

from db.models import Payment, Split, Transaction
from repositories.base import BaseRepository
from schemas.transaction import Transaction as TransactionDraft


class TransactionRepository(BaseRepository[Transaction]):
    """
    Repository for transaction-related operations.
    """

    model = Transaction

    async def create(self, obj: TransactionDraft) -> Transaction:
        transaction = Transaction(
            category_id=obj.category_id,
            room_id=obj.room_id,  # TODO -> Validate creator is in room
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

        await self._commit_and_refresh(transaction)

        return transaction
