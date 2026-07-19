from abc import ABC
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, delete
from sqlalchemy.engine import Row
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.orm.interfaces import ORMOption
from sqlalchemy.sql.elements import ColumnElement

from db.models import Base
from db.context import get_current_session


class BaseRepository[T: Base](ABC):
    """
    Provides common methods for CRUD operations.

    args:
        commit: Whether to commit the transaction after the operation.
        refresh: Whether to refresh the object after the operation.
    """

    model: type[T]

    def __init__(self, commit: bool = True, refresh: bool = True):
        self.commit = commit
        self.refresh = refresh

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "model" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must define a 'model' class attribute")

    @property
    def session(self):
        return get_current_session()

    async def create(self, obj: T) -> T:
        self.session.add(obj)
        await self._commit_and_refresh(obj)

        return obj

    async def find_all(
        self,
        columns: Sequence[InstrumentedAttribute[Any]] | None = None,
    ) -> Sequence[T] | Sequence[Any] | Sequence[Row[tuple[Any, ...]]]:
        """
        Fetch all rows for the repository model or a selected set of columns.

        Args:
            columns: Optional sequence of SQLAlchemy model attributes such as
                `User.id` or `[User.id, User.name]`.

        Returns:
            - `Sequence[T]` when `columns` is omitted.
            - `Sequence[Any]` when `columns` contains exactly one attribute.
            - `Sequence[Row[tuple[Any, ...]]]` when `columns` contains multiple
              attributes, in the same order they were requested.

        Examples:
            `await user_repo.find_all()`
                Returns: `[User(...), User(...)]`

            `await user_repo.find_all(columns=[User.id])`
                Returns: `[1, 2, 3]`

            `await user_repo.find_all(columns=[User.id, User.name])`
                Returns: `[(1, "alice"), (2, "bob")]`
        """
        stmt, is_scalar_result = self._build_select(columns)

        if is_scalar_result:
            result = await self.session.scalars(stmt)
        else:
            result = await self.session.execute(stmt)

        return result.all()

    async def find(
        self,
        filters: Sequence[ColumnElement[bool]] | None = None,
        columns: Sequence[InstrumentedAttribute[Any]] | None = None,
        options: Sequence[ORMOption] | None = None,
    ) -> T | Any | Row[tuple[Any, ...]] | None:
        """
        Fetch the first row matching the given filters.

        This helper is intended for simple repository lookups where you need
        optional filtering, column selection, or ORM loading options. For more
        complex queries with explicit joins, aliases, aggregates, or custom row
        shapes, prefer a repository-specific method instead of forcing that
        logic into this generic helper.

        Args:
            filters: Optional sequence of SQLAlchemy filter expressions such as
                `[User.id == 1]` or `[User.username == "alice"]`.
            columns: Optional sequence of SQLAlchemy model attributes such as
                `User.id` or `[User.id, User.name]`.
            options: Optional sequence of ORM loader options such as
                `[joinedload(Account.user)]`.

        Returns:
            - `T | None` when `columns` is omitted.
            - `Any | None` when `columns` contains exactly one attribute.
            - `Row[tuple[Any, ...]] | None` when `columns` contains multiple
              attributes, in the same order they were requested.

        Examples:
            `await user_repo.find(filters=[User.id == 1])`
                Returns: `User(...)` or `None`

            `await user_repo.find(filters=[User.id == 1], columns=[User.name])`
                Returns: `"alice"` or `None`

            `await user_repo.find(filters=[User.id == 1], columns=[User.id, User.name])`
                Returns: `(1, "alice")` or `None`

            `await account_repo.find(
                filters=[Account.uid == "123"],
                options=[joinedload(Account.user)],
            )`
                Returns: `Account(...)` with `user` eagerly loaded, or `None`
        """
        stmt, is_scalar_result = self._build_select(columns)

        if options:
            stmt = stmt.options(*options)

        if filters:
            stmt = stmt.where(*filters)

        if is_scalar_result:
            return await self.session.scalar(stmt)

        result = await self.session.execute(stmt)

        return result.first()

    async def get_by_id(self, obj_id: int) -> T | None:
        result = await self.session.get(self.model, obj_id)

        return result

    async def update(self, obj: T) -> T:
        updated_obj = await self.session.merge(obj)
        await self._commit_and_refresh(updated_obj)

        return updated_obj

    async def delete(self, obj: T) -> None:
        await self.session.delete(obj)
        await self._commit()

    async def delete_by_id(self, obj_id: int) -> None:
        await self.session.execute(delete(self.model).where(self.model.id == obj_id))
        await self._commit()

    def _build_select(
        self,
        columns: Sequence[InstrumentedAttribute[Any]] | None = None,
    ) -> tuple[Any, bool]:
        if not columns:
            return select(self.model), True

        if len(columns) == 1:
            return select(columns[0]), True

        return select(*columns), False

    async def _commit(self) -> None:
        if self.commit:
            try:
                await self.session.commit()
            except Exception as e:
                await self.session.rollback()
                raise e

    async def _commit_and_refresh(self, obj: T) -> None:
        await self._commit()

        if self.refresh:
            await self.session.refresh(obj)
