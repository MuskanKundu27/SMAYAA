import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.scripts.create_platform_admin import create
from tests.helpers import login

GOOD_PASSWORD = "Strong-pass-2026"


def test_created_admin_can_log_in_with_platform_permissions(
    client: TestClient, owner_db: Session
) -> None:
    create(owner_db, "Platform1", "Platform One", GOOD_PASSWORD)

    headers = login(client, "platform1", GOOD_PASSWORD)
    me = client.get("/api/v1/me", headers=headers).json()

    assert "config.manage" in me["permissions"]
    assert owner_db.query(AuditLog).filter_by(entity="user", action="create").count() == 1


def test_weak_password_and_taken_username_are_rejected(owner_db: Session) -> None:
    with pytest.raises(ValueError, match="at least 10"):
        create(owner_db, "platform1", "P", "short1")
    create(owner_db, "platform1", "P", GOOD_PASSWORD)
    with pytest.raises(ValueError, match="already taken"):
        create(owner_db, "PLATFORM1", "P", GOOD_PASSWORD)
