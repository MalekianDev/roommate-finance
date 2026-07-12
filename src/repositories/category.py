from repositories.base import BaseRepository
from db.models import Category


class CategoryRepository(BaseRepository[Category]):
    """
    Repository for category-related operations.
    """

    model = Category
