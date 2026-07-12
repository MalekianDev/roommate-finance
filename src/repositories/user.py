from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.enums import ProviderEnum
from db.models import Account, User
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """
    Repository for user-related operations.
    """

    model = User

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
        account = Account(user_id=user.id, provider=provider, uid=uid)

        self.session.add(user)
        self.session.add(account)

        try:
            await self.session.flush()
            await self._commit_and_refresh(user)
        except IntegrityError as e:
            error = str(e.orig)
            if "users_username_key" in error:
                raise ValueError("Username already taken.")
            if "accounts_provider_uid" in error:
                raise ValueError("Account already registered.")
            raise

        return user
