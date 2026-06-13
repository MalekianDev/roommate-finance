from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from settings import Settings

settings = Settings()

engine = create_async_engine(settings.db_url, echo=settings.debug_mode)
session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    async with session_maker() as session:
        yield session
