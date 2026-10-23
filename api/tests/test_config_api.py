"""Super admin configuration API: parameters, formulas, rules, modules, treatments."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog
from tests.helpers import Tenant, login, make_tenant, make_user, with_template

Call = Callable[..., Any]


@pytest.fixture
def acme(owner_db: Session) -> Tenant:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    make_user(owner_db, "root", "super_admin")
    return tenant


@pytest.fixture
def api(client: TestClient, acme: Tenant) -> Call:
    """Call the company's configuration API as the super admin."""
    headers = login(client, "root")
    base = f"/api/v1/companies/{acme.company_id}"

    def call(method: str, path: str, **kwargs: Any) -> Any:
        return client.request(method, base + path, headers=headers, **kwargs)

    return call


def calculated(key: str, formula: str, **extra: Any) -> dict[str, Any]:
    return {"key": key, "label": key.title(), "group_key": "chemistry", "kind": "calculated",
            "formula": formula, **extra}  # fmt: skip


def error_message(response: Any) -> str:
    return str(response.json()["error"]["message"])


# --- Parameters and formulas -------------------------------------------------------------------


def test_super_admin_adds_a_calculation(api: Call, owner_db: Session) -> None:
    response = api("POST", "/parameters", json=calculated("cycles", "cond / 300"))

    assert response.status_code == 201, response.text
    assert response.json()["formula_version"] == 1
    keys = [p["key"] for p in api("GET", "/parameters").json()]
    assert "cycles" in keys
    assert "parameter.create" in owner_db.scalars(select(AuditLog.action)).all()


@pytest.mark.parametrize(
    ("formula", "message"),
    [
        ("cond / nothing", "Unknown or inactive parameter(s): nothing"),
        ("__import__('os')", "Unknown function"),
        ("cond.real", "not allowed"),
        ("cycles + 1", "cannot use its own parameter"),
        ("ph / (ts - ts)", "no result with the sample values"),
        ("cond +", "Syntax error"),
    ],
)
def test_invalid_formulas_are_rejected(api: Call, formula: str, message: str) -> None:
    response = api("POST", "/parameters", json=calculated("cycles", formula))

    assert response.status_code == 422
    assert message in error_message(response)
    assert response.json()["error"]["details"][0]["field"] == "formula"


def test_circular_formulas_are_rejected(api: Call) -> None:
    assert api("POST", "/parameters", json=calculated("x", "range + 1")).status_code == 201

    response = api("PATCH", "/parameters/range", json={"formula": "x - 1"})

    assert response.status_code == 422
    assert "Circular reference between: range, x" in error_message(response)


@pytest.mark.parametrize("key", ["base", "min", "off"])
def test_reserved_names_cannot_be_keys(api: Call, key: str) -> None:
    body = {"key": key, "label": "X", "group_key": "chemistry", "kind": "input"}

    assert api("POST", "/parameters", json=body).status_code == 422


def test_duplicate_keys_are_rejected(api: Call) -> None:
    body = {"key": "ph", "label": "pH again", "group_key": "chemistry", "kind": "input"}

    assert api("POST", "/parameters", json=body).status_code == 409


def test_changing_a_formula_increments_its_version(api: Call) -> None:
    response = api("PATCH", "/parameters/range", json={"formula": "abs(tr - ts)"})

    assert response.status_code == 200
    assert response.json()["formula_version"] == 2


def test_parameters_used_by_formulas_or_rules_cannot_be_deactivated(api: Call) -> None:
    response = api("PATCH", "/parameters/ts", json={"is_active": False})

    assert response.status_code == 409
    users = {d["message"] for d in response.json()["error"]["details"]}
    assert users == {"parameter 'appr'", "parameter 'heat'", "parameter 'range'"}

    response = api("PATCH", "/parameters/hard", json={"is_active": False})
    users = {d["message"] for d in response.json()["error"]["details"]}
    assert {"parameter 'lsi'", "rule 'TH-P01'", "rule 'TH-P02'"} <= users


def test_unused_parameters_can_be_deactivated_and_reactivated(api: Call) -> None:
    # tssout (outlet TSS) is shown on screens but used by no formula or rule.
    assert (
        api("PATCH", "/parameters/tssout", json={"is_active": False}).json()["is_active"] is False
    )
    assert api("PATCH", "/parameters/tssout", json={"is_active": True}).json()["is_active"] is True


def test_default_limits_can_be_changed_and_must_be_ordered(api: Call) -> None:
    good = {"warn_min": 6.5, "good_min": 7.0, "good_max": 8.0, "warn_max": 9.0}
    bad = {"warn_min": 9.0, "good_min": 7.0, "good_max": 8.0, "warn_max": 6.5}

    assert api("PATCH", "/parameters/ph", json={"default_limits": good}).status_code == 200
    assert api("PATCH", "/parameters/ph", json={"default_limits": bad}).status_code == 422


def test_formula_test_uses_sample_values_or_given_values(api: Call) -> None:
    sample = api("POST", "/formulas/test", json={"formula": "tr - ts"}).json()
    given = api(
        "POST", "/formulas/test", json={"formula": "range * 2", "values": {"tr": 40, "ts": 30}}
    )
    broken = api("POST", "/formulas/test", json={"formula": "nope + 1"}).json()

    assert sample == {"ok": True, "result": 8.0, "references": ["tr", "ts"], "error": None}
    assert given.json()["result"] == 20.0
    assert broken["ok"] is False
    assert "nope" in broken["error"]


def test_tenant_users_cannot_use_the_configuration_api(client: TestClient, acme: Tenant) -> None:
    for username in ("acme-admin", "acme-manager", "acme-operator"):
        response = client.get(
            f"/api/v1/companies/{acme.company_id}/parameters", headers=login(client, username)
        )
        assert response.status_code == 403, username


# --- Rules -------------------------------------------------------------------------------------


def rule(code: str, condition: str, probability: str = "50") -> dict[str, Any]:
    return {"code": code, "title": code, "condition_expr": condition,
            "probability_expr": probability, "affects_modules": ["thermal"]}  # fmt: skip


def test_rules_are_validated_and_versioned(api: Call) -> None:
    assert api("POST", "/rules", json=rule("X-1", "off('nothing')")).status_code == 422
    assert api("POST", "/rules", json=rule("X-1", "open('x')")).status_code == 422
    assert api("POST", "/rules", json=rule("X-1", "off('fan')")).status_code == 201
    assert api("POST", "/rules", json=rule("X-1", "off('fan')")).status_code == 409

    updated = api("PATCH", "/rules/X-1", json={"condition_expr": "off('fan') and off('ts')"})

    assert updated.json()["version"] == 2


def test_rule_test_evaluates_with_default_limits(api: Call) -> None:
    values = {"hard": 900, "ts": 31, "tr": 39, "wbt": 26, "pin": 2.4, "pout": 1.8}
    response = api("POST", "/rules/test", json={
        "condition_expr": "count_off(['hard']) > 0",
        "probability_expr": "min(95, 15 + 20 * count_off(['hard']) + sev('hard'))",
        "values": values,
    })  # fmt: skip

    assert response.json()["matched"] is True
    assert response.json()["probability"] == 75.0  # 15 + 20 + 40 (hardness 900 is "bad")


# --- Modules -----------------------------------------------------------------------------------


def test_module_layouts_are_validated(api: Call) -> None:
    bad_widget = {
        "key": "overview",
        "title": "Overview",
        "layout": {"widgets": [{"type": "magic"}]},
    }
    assert api("POST", "/modules", json=bad_widget).status_code == 422

    layout = {"widgets": [{"type": "value_tiles", "params": ["ph", "ghost"]}]}
    response = api(
        "POST", "/modules", json={"key": "overview", "title": "Overview", "layout": layout}
    )

    assert response.status_code == 201
    assert response.json()["warnings"] == ["Widget 1: parameter 'ghost' is missing or inactive."]


def test_a_new_calculation_can_be_added_to_a_module_without_code_changes(api: Call) -> None:
    api("POST", "/parameters", json=calculated("cycles", "cond / 300"))
    layout = {"widgets": [{"type": "value_tiles", "params": ["dp", "rem", "bw", "cycles"]}]}

    response = api("PATCH", "/modules/filter", json={"layout": layout})

    assert response.status_code == 200
    assert response.json()["layout"]["widgets"][0]["params"][-1] == "cycles"
    assert response.json()["warnings"] == []


# --- Treatments --------------------------------------------------------------------------------


def test_template_treatments_are_flagged_for_review_and_can_be_edited(api: Call) -> None:
    treatments = api("GET", "/treatments").json()
    assert treatments and all(t["needs_review"] for t in treatments)

    body = [
        {
            "parameter_key": "hard",
            "direction": "high",
            "cause": "Reviewed cause",
            "treatment": "Reviewed treatment",
            "precautions": "Reviewed",
            "needs_review": False,
        }
    ]
    updated = {
        (t["parameter_key"], t["direction"]): t for t in api("PUT", "/treatments", json=body).json()
    }

    assert updated[("hard", "high")]["cause"] == "Reviewed cause"
    assert updated[("hard", "high")]["needs_review"] is False
    assert api("PUT", "/treatments", json=[{**body[0], "parameter_key": "zzz"}]).status_code == 422
