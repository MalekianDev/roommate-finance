from sqlalchemy import select

from db.context import get_current_session
from db.models import Category


class CategoryRepository:
    """
    Repository for category-related operations.
    """

    @property
    def session(self):
        return get_current_session()

    async def create_category(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.commit()
        return category

    async def get_all_categories(self) -> list[Category]:
        result = await self.session.scalars(select(Category))
        return list(result)
