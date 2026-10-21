"""Operator profiles (manager restricts operators) and the audit log listing."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.scripts.create_platform_admin import create as create_platform_admin
from tests.helpers import Tenant, login, make_tenant, make_user, with_template


@pytest.fixture
def acme(owner_db: Session) -> Tenant:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    return tenant


def profiles_url(tenant: Tenant) -> str:
    return f"/api/v1/plants/{tenant.plant_a.id}/operator-profiles"


# --- Operator profiles -------------------------------------------------------------------------


def test_manager_sees_operators_with_default_profiles(client: TestClient, acme: Tenant) -> None:
    body = client.get(profiles_url(acme), headers=login(client, "acme-manager")).json()

    assert [p["username"] for p in body] == ["acme-operator"]
    assert body[0]["is_default"] is True
    assert body[0]["visible_modules"] is None
    assert body[0]["can_edit_readings"] is True


def test_manager_restricts_an_operator_and_it_is_enforced(client: TestClient, acme: Tenant) -> None:
    manager = login(client, "acme-manager")
    url = f"{profiles_url(acme)}/{acme.operator.id}"

    response = client.put(
        url,
        json={"visible_modules": ["water_chemistry"], "can_edit_readings": False},
        headers=manager,
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_default"] is False
    operator = login(client, "acme-operator")
    base = f"/api/v1/plants/{acme.plant_a.id}"
    keys = [m["key"] for m in client.get(f"{base}/modules", headers=operator).json()]
    assert keys == ["water_chemistry"]
    saved = client.post(f"{base}/readings", json={"values": {"hard": 700}}, headers=operator)
    assert saved.status_code == 403

    reset = client.delete(url, headers=manager)
    assert reset.json()["is_default"] is True
    keys = [m["key"] for m in client.get(f"{base}/modules", headers=operator).json()]
    assert "filter" in keys


def test_unknown_modules_are_rejected(client: TestClient, acme: Tenant) -> None:
    response = client.put(
        f"{profiles_url(acme)}/{acme.operator.id}",
        json={"visible_modules": ["nope"]},
        headers=login(client, "acme-manager"),
    )
    assert response.status_code == 422


def test_profiles_only_for_lower_users_at_own_plant(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    other = make_user(owner_db, "acme-op-b", "operator", acme.company, acme.plant_b)
    manager = login(client, "acme-manager")

    # Another plant's operator, and the manager themselves, are not manageable here.
    for user_id in (other.id, acme.manager.id):
        response = client.put(f"{profiles_url(acme)}/{user_id}", json={}, headers=manager)
        assert response.status_code == 404
    b_url = f"/api/v1/plants/{acme.plant_b.id}/operator-profiles"
    assert client.get(b_url, headers=manager).status_code == 404


def test_operators_and_company_admins_cannot_manage_profiles(
    client: TestClient, acme: Tenant
) -> None:
    for user in ("acme-operator", "acme-admin"):
        response = client.get(profiles_url(acme), headers=login(client, user))
        assert response.status_code == 403


def test_other_company_cannot_touch_profiles(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    make_tenant(owner_db, "beta")
    response = client.put(
        f"{profiles_url(acme)}/{acme.operator.id}", json={}, headers=login(client, "beta-manager")
    )
    assert response.status_code in (403, 404)


# --- Audit log ---------------------------------------------------------------------------------


def test_company_admin_sees_only_own_company_entries(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    make_tenant(owner_db, "beta")
    client.put(
        f"{profiles_url(acme)}/{acme.operator.id}",
        json={"show_alerts": False},
        headers=login(client, "acme-manager"),
    )
    client.post(
        "/api/v1/plants", json={"name": "Beta Plant C"}, headers=login(client, "beta-admin")
    )

    body = client.get("/api/v1/audit-log", headers=login(client, "acme-admin")).json()

    assert body["total"] >= 1
    assert {e["company_id"] for e in body["items"]} == {str(acme.company_id)}
    entry = next(e for e in body["items"] if e["entity"] == "operator_profile")
    assert entry["actor_name"] == "Acme-Manager"
    assert entry["after"]["show_alerts"] is False


def test_platform_admin_sees_all_and_can_filter(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    create_platform_admin(owner_db, "platform1", "Platform One", "Strong-pass-2026")
    beta = make_tenant(owner_db, "beta")
    for user in ("acme-admin", "beta-admin"):
        client.post("/api/v1/plants", json={"name": f"{user} plant"}, headers=login(client, user))
    headers = login(client, "platform1", "Strong-pass-2026")

    everything = client.get("/api/v1/audit-log", headers=headers).json()
    only_beta = client.get(
        "/api/v1/audit-log", params={"company_id": str(beta.company_id)}, headers=headers
    ).json()

    companies = {e["company_name"] for e in everything["items"]}
    assert {"Acme Ltd", "Beta Ltd"} <= companies
    assert {e["company_name"] for e in only_beta["items"]} == {"Beta Ltd"}


def test_plant_users_cannot_read_the_audit_log(client: TestClient, acme: Tenant) -> None:
    for user in ("acme-manager", "acme-operator"):
        response = client.get("/api/v1/audit-log", headers=login(client, user))
        assert response.status_code == 403
