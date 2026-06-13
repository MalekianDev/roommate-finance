from contextvars import ContextVar
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import session_maker

_session_ctx: ContextVar[AsyncSession | None] = ContextVar("session", default=None)


class DBContext:
    """
    An async context manager to automatically open, bind, and clean up sessions.
    """

    async def __aenter__(self):
        self.session = session_maker()
        self.token = _session_ctx.set(self.session)
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                await self.session.rollback()  # Auto-rollback on any exception
        finally:
            await self.session.close()
            _session_ctx.reset(self.token)


def get_current_session() -> AsyncSession:
    """
    Helper for repositories to grab the current active session.
    """
    
    session = _session_ctx.get()
    if session is None:
        raise RuntimeError("No active database session context found!")
    return session
