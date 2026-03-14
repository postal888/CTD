import asyncio
import logging

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, text

from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

# Async engine for the API
async_engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine for indexing script
sync_engine = create_engine(settings.database_url_sync, echo=False)

# Retry on startup (Docker DNS may not resolve "db" immediately)
_INIT_RETRIES = 5
_INIT_DELAY_SEC = 3


async def init_db():
    """Create tables and pgvector extension. Retries on connection errors (e.g. DNS)."""
    last_err = None
    for attempt in range(1, _INIT_RETRIES + 1):
        try:
            async with async_engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception as e:
            last_err = e
            logger.warning("init_db attempt %s/%s failed: %s", attempt, _INIT_RETRIES, e)
            if attempt < _INIT_RETRIES:
                await asyncio.sleep(_INIT_DELAY_SEC)
    raise last_err


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
