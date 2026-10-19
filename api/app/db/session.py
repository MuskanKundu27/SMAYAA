from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db import tenant  # noqa: F401  (registers the RLS settings listener on Session)


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards.

    The session starts with no tenant context (sees nothing under RLS). get_principal sets
    the context once the user is known; see app/db/tenant.py.
    """
    with get_sessionmaker()() as session:
        yield session
