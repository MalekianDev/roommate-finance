import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from db.enums import ProviderEnum


class Base(DeclarativeBase):
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class BaseTimeStamp(Base):
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(BaseTimeStamp):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    accounts: Mapped[list["Account"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="paid_by", foreign_keys="Payment.paid_by_id")
    splits: Mapped[list["Split"]] = relationship(back_populates="owed_by", foreign_keys="Split.owed_by_id")

    created_rooms: Mapped[list["Room"]] = relationship(back_populates="created_by", foreign_keys="Room.created_by_id")
    room_memberships: Mapped[list["RoomMember"]] = relationship(
        back_populates="user",
        foreign_keys="RoomMember.user_id",
    )
    added_memberships: Mapped[list["RoomMember"]] = relationship(
        back_populates="added_by",
        foreign_keys="RoomMember.added_by_id",
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("provider", "uid"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[ProviderEnum] = mapped_column(SAEnum(ProviderEnum), nullable=False)
    uid: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="accounts")


class Room(BaseTimeStamp):
    __tablename__ = "rooms"

    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    invite_token: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    ) # TODO -> Develop an mechanism to rotate invite token

    created_by: Mapped["User"] = relationship(back_populates="created_rooms", foreign_keys=[created_by_id])
    members: Mapped[list["RoomMember"]] = relationship(back_populates="room")


class RoomMember(BaseTimeStamp):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_member"),)

    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    added_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    room: Mapped["Room"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="room_memberships", foreign_keys=[user_id])
    added_by: Mapped["User | None"] = relationship(back_populates="added_memberships", foreign_keys=[added_by_id])


class Category(Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)


class Transaction(BaseTimeStamp):
    __tablename__ = "transactions"

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    category: Mapped["Category"] = relationship()
    created_by: Mapped["User"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="transaction")
    splits: Mapped[list["Split"]] = relationship(back_populates="transaction")


class Payment(BaseTimeStamp):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("transaction_id", "paid_by_id"),)

    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    paid_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="payments")
    paid_by: Mapped["User"] = relationship(foreign_keys=[paid_by_id], back_populates="payments")
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])


class Split(BaseTimeStamp):
    __tablename__ = "splits"
    __table_args__ = (UniqueConstraint("transaction_id", "owed_by_id"),)

    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    owed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="splits")
    owed_by: Mapped["User"] = relationship(foreign_keys=[owed_by_id], back_populates="splits")
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
