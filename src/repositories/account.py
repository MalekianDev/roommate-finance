from sqlalchemy import select
from sqlalchemy.orm import joinedload

from db.models import Account
from db.enums import ProviderEnum
from repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    model = Account

    async def get_by_chat_id(self, chat_id: int) -> Account | None:
        """
        Get a account with user loaded by their Telegram chat ID.
        """
        return await self.session.scalar(
            select(Account)
            .options(joinedload(Account.user))
            .where(
                Account.provider == ProviderEnum.TELEGRAM,
                Account.uid == str(chat_id),
            )
        )
