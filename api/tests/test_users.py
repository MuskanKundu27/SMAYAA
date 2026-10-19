import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.helpers import login, make_tenant, make_user

STRONG = "Strong-pass-123"


def new_user(role: str, plant_id: uuid.UUID | None = None, username: str = "newbie") -> dict:  # type: ignore[type-arg]
    body = {"username": username, "full_name": "New Person", "password": STRONG, "role": role}
    if plant_id:
        body["plant_id"] = str(plant_id)
    return body


# --- Rank rule ------------------------------------------------------------------------------


def test_manager_creates_an_operator_in_own_plant(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")

    response = client.post(
        "/api/v1/users",
        json=new_user("operator", tenant.plant_a.id),
        headers=login(client, "acme-manager"),
    )

    assert response.status_code == 201, response.text
    assert response.json()["roles"] == ["operator"]
    assert response.json()["plant_ids"] == [str(tenant.plant_a.id)]
    login(client, "newbie", STRONG)  # the new operator can log in


def test_manager_cannot_create_a_manager(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")

    response = client.post(
        "/api/v1/users",
        json=new_user("manager", tenant.plant_a.id),
        headers=login(client, "acme-manager"),
    )

    assert response.status_code == 403


def test_manager_cannot_create_users_in_another_plant(
    client: TestClient, owner_db: Session
) -> None:
    tenant = make_tenant(owner_db, "acme")

    response = client.post(
        "/api/v1/users",
        json=new_user("operator", tenant.plant_b.id),
        headers=login(client, "acme-manager"),
    )

    assert response.status_code == 404


def test_operator_cannot_create_users(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")

    response = client.post(
        "/api/v1/users",
        json=new_user("operator", tenant.plant_a.id),
        headers=login(client, "acme-operator"),
    )

    assert response.status_code == 403


def test_company_admin_creates_a_manager_but_not_another_company_admin(
    client: TestClient, owner_db: Session
) -> None:
    tenant = make_tenant(owner_db, "acme")
    headers = login(client, "acme-admin")

    manager = client.post(
        "/api/v1/users", json=new_user("manager", tenant.plant_b.id), headers=headers
    )
    admin = client.post(
        "/api/v1/users", json=new_user("company_admin", username="admin2"), headers=headers
    )

    assert manager.status_code == 201
    assert admin.status_code == 403


def test_super_admin_creates_a_company_admin_for_a_company(
    client: TestClient, owner_db: Session
) -> None:
    tenant = make_tenant(owner_db, "acme")
    make_user(owner_db, "root", "super_admin")
    body = {**new_user("company_admin"), "company_id": str(tenant.company_id)}

    response = client.post("/api/v1/users", json=body, headers=login(client, "root"))

    assert response.status_code == 201
    assert response.json()["company_id"] == str(tenant.company_id)


def test_super_admin_cannot_create_plant_users(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")
    make_user(owner_db, "root", "super_admin")

    response = client.post(
        "/api/v1/users", json=new_user("operator", tenant.plant_a.id), headers=login(client, "root")
    )

    assert response.status_code == 403


# --- Validation -----------------------------------------------------------------------------


def test_weak_password_is_rejected_with_reasons(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")
    body = {**new_user("operator", tenant.plant_a.id), "password": "short"}

    response = client.post("/api/v1/users", json=body, headers=login(client, "acme-manager"))

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "password"


def test_usernames_are_unique_across_companies(client: TestClient, owner_db: Session) -> None:
    make_tenant(owner_db, "beta")
    tenant = make_tenant(owner_db, "acme")
    body = new_user("operator", tenant.plant_a.id, username="BETA-operator")

    response = client.post("/api/v1/users", json=body, headers=login(client, "acme-manager"))

    assert response.status_code == 409


# --- Listing --------------------------------------------------------------------------------


def test_manager_lists_only_users_of_own_plant(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")
    make_user(owner_db, "b-operator", "operator", tenant.company, tenant.plant_b)

    response = client.get("/api/v1/users", headers=login(client, "acme-manager"))

    names = {u["username"] for u in response.json()["items"]}
    assert names == {"acme-manager", "acme-operator"}


def test_company_admin_lists_all_users_of_the_company(
    client: TestClient, owner_db: Session
) -> None:
    make_tenant(owner_db, "acme")
    make_tenant(owner_db, "beta")

    response = client.get("/api/v1/users", headers=login(client, "acme-admin"))

    assert response.json()["total"] == 3
    assert all(u["username"].startswith("acme-") for u in response.json()["items"])


# --- Deactivation ---------------------------------------------------------------------------


def test_manager_deactivates_an_operator_who_is_then_locked_out(
    client: TestClient, owner_db: Session
) -> None:
    tenant = make_tenant(owner_db, "acme")
    operator_headers = login(client, "acme-operator")

    response = client.delete(
        f"/api/v1/users/{tenant.operator.id}", headers=login(client, "acme-manager")
    )

    assert response.status_code == 200
    assert response.json()["user"]["is_active"] is False
    assert response.json()["warnings"] == []
    assert client.get("/api/v1/me", headers=operator_headers).status_code == 401


def test_operator_cannot_deactivate_anyone(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")

    response = client.delete(
        f"/api/v1/users/{tenant.manager.id}", headers=login(client, "acme-operator")
    )

    assert response.status_code == 403


def test_manager_cannot_deactivate_another_manager(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")
    other = make_user(owner_db, "acme-manager2", "manager", tenant.company, tenant.plant_a)

    response = client.delete(f"/api/v1/users/{other.id}", headers=login(client, "acme-manager"))

    assert response.status_code == 403


def test_nobody_can_deactivate_themselves(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")

    response = client.delete(
        f"/api/v1/users/{tenant.admin.id}", headers=login(client, "acme-admin")
    )

    assert response.status_code == 409


def test_deactivating_the_last_manager_warns_that_the_plant_has_no_manager(
    client: TestClient, owner_db: Session
) -> None:
    tenant = make_tenant(owner_db, "acme")

    response = client.delete(
        f"/api/v1/users/{tenant.manager.id}", headers=login(client, "acme-admin")
    )

    assert response.status_code == 200
    assert response.json()["warnings"] == [
        "Plant 'Acme Plant A' has no manager now. The company admin can edit its limits "
        "until a new manager is assigned."
    ]
