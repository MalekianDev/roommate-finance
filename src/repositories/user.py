from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from db.enums import ProviderEnum
from db.models import Account, User
from db.context import get_current_session


class UserRepository:
    """
    Repository for user-related operations.
    """

    @property
    def session(self):
        return get_current_session()

    async def get_account_by_chat_id(self, chat_id: int) -> Account | None:
        """
        Get a user by their Telegram chat ID.
        """
        return await self.session.scalar(
            select(Account)
            .options(joinedload(Account.user))
            .where(
                Account.provider == ProviderEnum.TELEGRAM,
                Account.uid == str(chat_id),
            )
        )

    async def register_user(
        self,
        name: str,
        username: str,
        provider: ProviderEnum,
        uid: str,
    ) -> User:
        """
        Register a new user.
        """
        first_user = await self.session.scalar(select(User).limit(1))
        is_superuser = first_user is None

        user = User(name=name, username=username, is_superuser=is_superuser)

        try:
            self.session.add(user)
            await self.session.flush()

            account = Account(user_id=user.id, provider=provider, uid=uid)
            self.session.add(account)
            await self.session.commit()
            await self.session.refresh(user)

        except IntegrityError as e:
            await self.session.rollback()
            error = str(e.orig)
            if "users_username_key" in error:
                raise ValueError("Username already taken.")
            if "accounts_provider_uid" in error:
                raise ValueError("Account already registered.")
            raise

        return user

    async def get_all_users(self) -> list[User]:
        result = await self.session.scalars(select(User))
        return list(result)
