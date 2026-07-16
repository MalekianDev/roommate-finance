from sqlalchemy import select, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from db.enums import ProviderEnum
from db.models import Account, User, RoomMember
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
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
        is_superuser = not await self.session.scalar(select(exists().where(User.id.is_not(None))))

        user = User(name=name, username=username, is_superuser=is_superuser)
        self.session.add(user)
        await self.session.flush()

        self.session.add(
            Account(
                user=user,
                provider=provider,
                uid=uid,
            )
        )

        try:
            await self._commit_and_refresh(user)
        except IntegrityError as e:
            constraint = getattr(e.orig, "constraint_name", None)
            if constraint == "users_username_key":
                raise ValueError("Username already taken.")
            if constraint == "accounts_provider_uid_key":
                raise ValueError("Account already registered.")
            raise

        return user

    async def has_active_room(self, user_id: int) -> bool:
        """
        Check if a user belongs to at least one room that also has another member.
        """
        ROOM_MEMBER = RoomMember
        OTHER_MEMBER = aliased(RoomMember, name="other_member")

        has_active_room = await self.session.scalar(
            select(
                exists().where(
                    ROOM_MEMBER.user_id == user_id,
                    exists().where(
                        OTHER_MEMBER.room_id == ROOM_MEMBER.room_id,
                        OTHER_MEMBER.user_id != user_id,
                    ),
                )
            )
        )

        return bool(has_active_room)
