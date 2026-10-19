from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog
from tests.helpers import login, make_tenant, make_user

NEW_COMPANY = {
    "name": "Gamma Power",
    "admin": {"username": "gamma-admin", "full_name": "G Admin", "password": "Gamma-pass-123"},
}


def test_super_admin_creates_a_company_with_its_first_admin(
    client: TestClient, owner_db: Session
) -> None:
    make_user(owner_db, "root", "super_admin")

    response = client.post("/api/v1/companies", json=NEW_COMPANY, headers=login(client, "root"))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["company"]["name"] == "Gamma Power"
    assert body["admin"]["roles"] == ["company_admin"]
    # The new admin can log in and sees their company.
    me = client.get("/api/v1/me", headers=login(client, "gamma-admin", "Gamma-pass-123")).json()
    assert me["company"]["name"] == "Gamma Power"
    actions = owner_db.scalars(select(AuditLog.action)).all()
    assert {"company.create", "user.create"} <= set(actions)


def test_company_names_are_unique(client: TestClient, owner_db: Session) -> None:
    make_tenant(owner_db, "acme")
    make_user(owner_db, "root", "super_admin")
    body = {**NEW_COMPANY, "name": "ACME LTD"}

    response = client.post("/api/v1/companies", json=body, headers=login(client, "root"))

    assert response.status_code == 409


def test_company_admin_cannot_create_companies(client: TestClient, owner_db: Session) -> None:
    make_tenant(owner_db, "acme")

    response = client.post(
        "/api/v1/companies", json=NEW_COMPANY, headers=login(client, "acme-admin")
    )

    assert response.status_code == 403


def test_deactivating_a_company_locks_out_its_users(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")
    make_user(owner_db, "root", "super_admin")
    operator_headers = login(client, "acme-operator")

    response = client.patch(
        f"/api/v1/companies/{tenant.company_id}",
        json={"is_active": False},
        headers=login(client, "root"),
    )

    assert response.status_code == 200
    assert client.get("/api/v1/me", headers=operator_headers).status_code == 401


def test_company_admin_creates_and_renames_a_plant(client: TestClient, owner_db: Session) -> None:
    make_tenant(owner_db, "acme")
    headers = login(client, "acme-admin")

    created = client.post("/api/v1/plants", json={"name": "Unit 3"}, headers=headers)
    assert created.status_code == 201
    renamed = client.patch(
        f"/api/v1/plants/{created.json()['id']}", json={"name": "Unit 3B"}, headers=headers
    )

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Unit 3B"


def test_plant_names_are_unique_within_a_company(client: TestClient, owner_db: Session) -> None:
    make_tenant(owner_db, "acme")

    response = client.post(
        "/api/v1/plants", json={"name": "Acme Plant A"}, headers=login(client, "acme-admin")
    )

    assert response.status_code == 409


def test_manager_cannot_create_plants(client: TestClient, owner_db: Session) -> None:
    make_tenant(owner_db, "acme")

    response = client.post(
        "/api/v1/plants", json={"name": "Sneaky"}, headers=login(client, "acme-manager")
    )

    assert response.status_code == 403
