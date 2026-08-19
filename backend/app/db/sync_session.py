"""Synchronous SQLAlchemy session, used by Celery workers and the seed script.

Celery's worker pool is process/thread based rather than asyncio-native, so workers use a
plain sync engine (psycopg2) instead of the asyncpg engine used by the FastAPI app.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True, pool_size=10, max_overflow=5)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, autoflush=False)


def get_sync_db() -> Session:
    return SyncSessionLocal()
