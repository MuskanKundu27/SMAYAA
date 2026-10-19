import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.helpers import login, make_tenant, make_user


def test_me_describes_the_user_scope_and_permissions(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")

    me = client.get("/api/v1/me", headers=login(client, "acme-manager")).json()

    assert me["username"] == "acme-manager"
    assert me["roles"] == ["manager"]
    assert me["company"]["name"] == "Acme Ltd"
    assert [p["id"] for p in me["plants"]] == [str(tenant.plant_a.id)]  # not plant B
    assert "limits.write" in me["permissions"]
    assert "users.manage:manager" not in me["permissions"]


def test_company_admin_sees_every_plant_of_the_company(
    client: TestClient, owner_db: Session
) -> None:
    make_tenant(owner_db, "acme")

    me = client.get("/api/v1/me", headers=login(client, "acme-admin")).json()

    assert sorted(p["name"] for p in me["plants"]) == ["Acme Plant A", "Acme Plant B"]


def test_super_admin_has_no_company_and_no_plants(client: TestClient, owner_db: Session) -> None:
    make_user(owner_db, "root", "super_admin")

    me = client.get("/api/v1/me", headers=login(client, "root")).json()

    assert me["company"] is None
    assert me["plants"] == []
    assert "companies.manage" in me["permissions"]
    assert "readings.read" not in me["permissions"]  # super admin never sees readings


@pytest.mark.parametrize(
    ("username", "path", "expected"),
    [
        ("acme-operator", "/api/v1/users", 403),
        ("acme-operator", "/api/v1/companies", 403),
        ("acme-manager", "/api/v1/companies", 403),
        ("acme-admin", "/api/v1/companies", 403),
        ("acme-manager", "/api/v1/users", 200),
        ("acme-admin", "/api/v1/users", 200),
        ("acme-operator", "/api/v1/plants", 200),
        ("root", "/api/v1/companies", 200),
        ("root", "/api/v1/plants", 403),
    ],
)
def test_endpoint_access_by_role(
    client: TestClient, owner_db: Session, username: str, path: str, expected: int
) -> None:
    make_tenant(owner_db, "acme")
    make_user(owner_db, "root", "super_admin")

    assert client.get(path, headers=login(client, username)).status_code == expected
