import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


def _use_test_database() -> None:
    """Point the app at the test database before anything creates an engine."""
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url is None:
        # Fall back to the value in the root .env (read via pydantic-settings' dotenv parser).
        from dotenv import dotenv_values

        from app.core.config import REPO_ROOT

        test_url = dotenv_values(REPO_ROOT / ".env", encoding="utf-8-sig").get("TEST_DATABASE_URL")
    if not test_url:
        raise RuntimeError("TEST_DATABASE_URL is not set (environment or .env)")
    os.environ["DATABASE_URL"] = test_url
    os.environ["ENVIRONMENT"] = "test"
    get_settings.cache_clear()


_use_test_database()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
