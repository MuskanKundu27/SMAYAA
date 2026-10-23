"""Plant limits and settings, including the company-admin fallback when a plant has no manager."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.db.tenant import ALL_PLANTS, TenantContext, set_tenant_context
from tests.helpers import Tenant, login, make_tenant, make_user, with_template

HARD = {"parameter_key": "hard", "warn_min": 100, "good_min": 200, "good_max": 700, "warn_max": 900}


@pytest.fixture
def acme(owner_db: Session) -> Tenant:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    return tenant


def limits_url(tenant: Tenant, plant: str = "a") -> str:
    plant_obj = tenant.plant_a if plant == "a" else tenant.plant_b
    return f"/api/v1/plants/{plant_obj.id}/limits"


def item(body: dict[str, Any], key: str) -> dict[str, Any]:
    return next(i for i in body["items"] if i["parameter_key"] == key)


def test_manager_sees_default_limits_and_can_edit(client: TestClient, acme: Tenant) -> None:
    body = client.get(limits_url(acme), headers=login(client, "acme-manager")).json()

    assert body["can_edit"] is True
    assert body["has_manager"] is True
    hard = item(body, "hard")
    assert hard["limits"] == {"warn_min": 100, "good_min": 200, "good_max": 600, "warn_max": 800}
    assert hard["source"] == "default"
    assert item(body, "wbt")["limits"] is None  # no limits defined


def test_manager_changes_a_limit_for_the_plant_only(client: TestClient, acme: Tenant) -> None:
    headers = login(client, "acme-manager")

    response = client.put(limits_url(acme), json={"items": [HARD]}, headers=headers)

    assert response.status_code == 200, response.text
    assert item(response.json(), "hard")["source"] == "plant"
    assert item(response.json(), "hard")["limits"]["good_max"] == 700
    # Plant B still uses the company default.
    other = client.get(limits_url(acme, "b"), headers=login(client, "acme-admin")).json()
    assert item(other, "hard")["source"] == "default"


def test_a_limit_can_be_reset_to_the_default(client: TestClient, acme: Tenant) -> None:
    headers = login(client, "acme-manager")
    client.put(limits_url(acme), json={"items": [HARD]}, headers=headers)

    response = client.delete(f"{limits_url(acme)}/hard", headers=headers)

    assert item(response.json(), "hard")["source"] == "default"


def test_limits_must_be_ordered(client: TestClient, acme: Tenant) -> None:
    bad = {**HARD, "good_min": 950}

    response = client.put(
        limits_url(acme), json={"items": [bad]}, headers=login(client, "acme-manager")
    )

    assert response.status_code == 422


def test_unknown_parameters_are_rejected(client: TestClient, acme: Tenant) -> None:
    bad = {**HARD, "parameter_key": "ghost"}

    response = client.put(
        limits_url(acme), json={"items": [bad]}, headers=login(client, "acme-manager")
    )

    assert response.status_code == 422


def test_operator_cannot_read_or_change_limits(client: TestClient, acme: Tenant) -> None:
    headers = login(client, "acme-operator")

    assert client.get(limits_url(acme), headers=headers).status_code == 403
    assert client.put(limits_url(acme), json={"items": [HARD]}, headers=headers).status_code == 403


def test_company_admin_can_edit_limits_only_while_the_plant_has_no_manager(
    client: TestClient, acme: Tenant
) -> None:
    admin = login(client, "acme-admin")

    # Plant A has a manager: view only.
    assert client.get(limits_url(acme), headers=admin).json()["can_edit"] is False
    refused = client.put(limits_url(acme), json={"items": [HARD]}, headers=admin)
    assert refused.status_code == 403
    assert "has a manager" in refused.json()["error"]["message"]

    # The admin deactivates the manager; the plant now has no manager.
    client.delete(f"/api/v1/users/{acme.manager.id}", headers=admin)

    body = client.get(limits_url(acme), headers=admin).json()
    assert body["has_manager"] is False
    assert body["can_edit"] is True
    assert client.put(limits_url(acme), json={"items": [HARD]}, headers=admin).status_code == 200


def test_company_admin_can_edit_a_plant_that_never_had_a_manager(
    client: TestClient, acme: Tenant
) -> None:
    response = client.put(
        limits_url(acme, "b"), json={"items": [HARD]}, headers=login(client, "acme-admin")
    )

    assert response.status_code == 200


def test_manager_cannot_see_another_plants_limits(client: TestClient, acme: Tenant) -> None:
    response = client.get(limits_url(acme, "b"), headers=login(client, "acme-manager"))

    assert response.status_code == 404


def test_another_companys_plant_is_not_found(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    beta = make_tenant(owner_db, "beta")
    with_template(owner_db, beta.company)

    response = client.get(limits_url(beta), headers=login(client, "acme-admin"))

    assert response.status_code == 404


def test_super_admin_cannot_read_plant_limits(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    make_user(owner_db, "root", "super_admin")

    assert client.get(limits_url(acme), headers=login(client, "root")).status_code == 403


# --- Plant settings ----------------------------------------------------------------------------


def settings_url(tenant: Tenant) -> str:
    return f"/api/v1/plants/{tenant.plant_a.id}/settings"


def test_baseline_comes_from_the_company_default_until_the_manager_sets_it(
    client: TestClient, acme: Tenant
) -> None:
    headers = login(client, "acme-manager")
    before = client.get(settings_url(acme), headers=headers).json()
    assert before["settings"]["clean_baseline_approach"] == {
        "value": 4.0,
        "source": "company_default",
    }

    response = client.put(
        settings_url(acme), json={"values": {"clean_baseline_approach": 4.5}}, headers=headers
    )

    assert response.json()["settings"]["clean_baseline_approach"] == {
        "value": 4.5,
        "source": "plant",
    }


@pytest.mark.parametrize(
    "values",
    [
        {"clean_baseline_approach": "four"},
        {"unknown_setting": 1},
        {"clean_baseline_approach": True},
    ],
)
def test_invalid_settings_are_rejected(
    client: TestClient, acme: Tenant, values: dict[str, Any]
) -> None:
    response = client.put(
        settings_url(acme), json={"values": values}, headers=login(client, "acme-manager")
    )

    assert response.status_code == 422


def test_company_admin_cannot_change_baseline_while_a_manager_exists(
    client: TestClient, acme: Tenant
) -> None:
    response = client.put(
        settings_url(acme), json={"values": {"clean_baseline_approach": 5}},
        headers=login(client, "acme-admin"),
    )  # fmt: skip

    assert response.status_code == 403


# --- Isolation in the database -----------------------------------------------------------------


def test_rls_keeps_configuration_and_limits_inside_the_company(
    app_engine: Engine, owner_db: Session, acme: Tenant
) -> None:
    beta = make_tenant(owner_db, "beta")
    with_template(owner_db, beta.company)
    context = TenantContext(user_id=beta.admin.id, company_id=beta.company_id, plant_ids=ALL_PLANTS)

    with Session(app_engine) as session:
        set_tenant_context(session, context)
        companies = (
            session.execute(text("SELECT DISTINCT company_id FROM parameters")).scalars().all()
        )
        own_plants = session.execute(text("SELECT count(*) FROM limits WHERE plant_id = :p"),
                                     {"p": acme.plant_a.id}).scalar()  # fmt: skip
    assert companies == [beta.company_id]
    assert own_plants == 0


def test_rls_lets_only_the_platform_change_configuration(app_engine: Engine, acme: Tenant) -> None:
    context = TenantContext(user_id=acme.admin.id, company_id=acme.company_id, plant_ids=ALL_PLANTS)

    with Session(app_engine) as session:
        set_tenant_context(session, context)
        changed = session.execute(
            text("UPDATE parameters SET label = 'hacked' WHERE company_id = :c"),
            {"c": acme.company_id},
        ).rowcount  # type: ignore[attr-defined]
        session.rollback()
    assert changed == 0


def test_plant_settings_come_from_the_template_and_feed_formulas(
    client: TestClient, acme: Tenant
) -> None:
    headers = login(client, "acme-manager")
    settings = client.get(settings_url(acme), headers=headers).json()["settings"]
    assert settings["design_flow"] == {"value": 1000.0, "source": "company_default"}
    assert settings["min_water_per_clean"]["value"] == 2.5

    client.post(
        f"/api/v1/plants/{acme.plant_a.id}/readings",
        json={"values": {"tr": 39, "ts": 31, "wbt": 26, "flow": 1000, "load": 100, "fanspd": 100}},
        headers=headers,
    )
    thermal = f"/api/v1/plants/{acme.plant_a.id}/modules/thermal"

    def expected_approach() -> float:
        view = client.get(thermal, headers=headers).json()
        tiles = {t["key"]: t for w in view["widgets"] for t in (w.get("tiles") or [])}
        return float(tiles["expappr"]["value"])

    assert expected_approach() == pytest.approx(4.0)  # design conditions: the clean baseline
    client.put(settings_url(acme), json={"values": {"design_flow": 500}}, headers=headers)
    # Flow is now twice the plant's design flow: the setting feeds the formula.
    assert expected_approach() == pytest.approx(4.0 * 2**0.2)
