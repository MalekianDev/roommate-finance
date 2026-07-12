from abc import ABC
from collections.abc import Sequence

from sqlalchemy import select, delete

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

    async def get_all(self) -> Sequence[T]:
        result = await self.session.scalars(select(self.model))

        return result.all()

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
