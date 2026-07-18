from db.models import User, Room, RoomMember
from repositories.base import BaseRepository


class RoomRepository(BaseRepository[Room]):
    model = Room

    async def register_room(self, name: str, created_by: User) -> Room:
        room = Room(
            name=name,
            created_by=created_by,
        )
        self.session.add(room)
        await self.session.flush()

        self.session.add(RoomMember(room=room, user=created_by))
        await self._commit_and_refresh(room)

        return room


class RoomMemberRepository(BaseRepository[RoomMember]):
    model = RoomMember
