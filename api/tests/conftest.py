"""Test setup.

- The app runs against the separate `smayaa_test` database, connecting as the runtime role
  (TEST_DATABASE_URL), so row-level security is active in tests exactly as in production.
- The schema is migrated once per test run with Alembic, as the owner role.
- After each test all tenant data is truncated (roles/permissions from the migration stay).
- Test data is created directly as the owner role (bypassing RLS), see tests/helpers.py.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings


def _setting(name: str) -> str:
    value = os.environ.get(name) or dotenv_values(REPO_ROOT / ".env", encoding="utf-8-sig").get(
        name
    )
    if not value:
        raise RuntimeError(f"{name} is not set (environment or .env)")
    return value


TEST_APP_URL = _setting("TEST_DATABASE_URL")
TEST_OWNER_URL = _setting("TEST_MIGRATION_DATABASE_URL")

# Must happen before anything creates the app's engine or caches settings.
os.environ["DATABASE_URL"] = TEST_APP_URL
os.environ["ENVIRONMENT"] = "test"
get_settings.cache_clear()

TENANT_TABLES = (
    "audit_log, refresh_tokens, readings, operator_profiles, limits, plant_settings, treatments,"
    " rules, modules, parameters, role_assignments, users, plants, companies"
)


@pytest.fixture(scope="session")
def owner_engine() -> Iterator[Engine]:
    os.environ["MIGRATION_DATABASE_URL"] = TEST_OWNER_URL
    command.upgrade(Config(str(Path(__file__).parents[1] / "alembic.ini")), "head")
    engine = create_engine(TEST_OWNER_URL)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(owner_engine: Engine) -> Iterator[None]:
    yield
    with owner_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TENANT_TABLES} CASCADE"))


@pytest.fixture
def owner_db(owner_engine: Engine) -> Iterator[Session]:
    """Session as the schema owner: bypasses RLS. Use only to arrange test data."""
    with Session(owner_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def app_engine() -> Iterator[Engine]:
    """Engine as the runtime role (RLS applies), for raw-SQL isolation tests."""
    engine = create_engine(TEST_APP_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
