from db.models import Room, RoomMember
from repositories.base import BaseRepository


class RoomRepository(BaseRepository[Room]):
    model = Room


class RoomMemberRepository(BaseRepository[RoomMember]):
    model = RoomMember
