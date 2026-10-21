"""The shipped default template must be valid on its own, and copying it must work."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.engine.calculation import (
    BASE,
    RuleContext,
    calculate,
    calculation_order,
    evaluate_rule,
    parse_rule,
    statuses_for,
)
from app.engine.evaluator import parse
from app.engine.status import Limits
from app.schemas.config import ModuleLayout
from app.templates.default import DEFAULT_TEMPLATE as T
from tests.helpers import login, make_tenant, make_user, with_template

KEYS = {p.key for p in T.parameters}
FORMULAS = {p.key: parse(p.formula) for p in T.parameters if p.formula}
SAMPLES = {p.key: p.sample for p in T.parameters if not p.formula}
BASELINE = T.plant_setting_defaults["clean_baseline_approach"]


def sample_context() -> RuleContext:
    values = {**SAMPLES, **calculate(SAMPLES, FORMULAS, BASELINE)}
    limits = {p.key: Limits(*p.limits) if p.limits else None for p in T.parameters}
    return RuleContext(values, statuses_for(values, limits))


def test_keys_are_unique() -> None:
    assert len(KEYS) == len(T.parameters)
    assert len({r.code for r in T.rules}) == len(T.rules)


def test_formulas_reference_only_template_parameters_and_have_no_loops() -> None:
    for key, expr in FORMULAS.items():
        assert expr.references <= KEYS | {BASE}, key
    calculation_order(FORMULAS)  # raises on a loop


def test_sample_values_give_the_expected_kpis() -> None:
    results = calculate(SAMPLES, FORMULAS, BASELINE)

    assert results["range"] == 8.0
    assert results["appr"] == 5.0
    assert results["heat"] == pytest.approx(9304.0)
    assert results["resid"] == 1.0
    assert results["dp"] == pytest.approx(0.6)
    assert results["rem"] == pytest.approx(83.333, rel=1e-3)
    assert results["bw"] == 3.0
    assert results["lsi"] == pytest.approx(0.6958, rel=1e-3)


def test_limits_are_ordered() -> None:
    for p in T.parameters:
        if p.limits:
            assert Limits(*p.limits).is_ordered(), p.key


def test_rules_parse_reference_known_parameters_and_evaluate() -> None:
    context = sample_context()
    for rule in T.rules:
        condition, probability = parse_rule(rule.condition), parse_rule(rule.probability)
        assert condition.references | probability.references <= KEYS, rule.code
        assert isinstance(evaluate_rule(condition, context), bool), rule.code
        assert isinstance(evaluate_rule(probability, context), float), rule.code


def test_sample_data_predicts_thermal_fouling_only() -> None:
    # Sample hardness 650 is above good max 600: thermal chemistry influence (TH-P02). The
    # filter chemistry list (tds, sio2, mic, cond) is all in range, so no filter problem.
    context = sample_context()
    matched = {r.code for r in T.rules if evaluate_rule(parse_rule(r.condition), context)}

    assert matched == {"TH-P02"}


def test_module_layouts_are_valid_and_reference_existing_items() -> None:
    codes = {r.code for r in T.rules}
    for module in T.modules:
        layout = ModuleLayout.model_validate({"widgets": module.widgets})
        for widget in layout.widgets:
            assert set(getattr(widget, "params", None) or []) <= KEYS, module.key
            assert set(getattr(widget, "rules", None) or []) <= codes, module.key


def test_treatments_reference_template_parameters() -> None:
    for treatment in T.treatments:
        assert treatment.key in KEYS
        assert treatment.direction in ("high", "low")


# --- Copying into companies --------------------------------------------------------------------


def test_new_companies_start_with_the_template(client: TestClient, owner_db: Session) -> None:
    make_user(owner_db, "root", "super_admin")
    headers = login(client, "root")
    body = {
        "name": "Gamma Power",
        "admin": {"username": "gamma-admin", "password": "Gamma-pass-123"},
    }
    company_id = client.post("/api/v1/companies", json=body, headers=headers).json()["company"][
        "id"
    ]

    params = client.get(f"/api/v1/companies/{company_id}/parameters", headers=headers).json()
    modules = client.get(f"/api/v1/companies/{company_id}/modules", headers=headers).json()
    rules = client.get(f"/api/v1/companies/{company_id}/rules", headers=headers).json()

    assert len(params) == len(T.parameters)
    assert [m["key"] for m in modules] == ["water_chemistry", "filter", "thermal"]
    assert all(m["warnings"] == [] for m in modules)
    assert [r["code"] for r in rules] == ["FLT-P01", "FLT-P02", "FLT-P03", "TH-P01", "TH-P02"]


def test_applying_the_template_again_adds_nothing(client: TestClient, owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    make_user(owner_db, "root", "super_admin")

    response = client.post(
        f"/api/v1/companies/{tenant.company_id}/apply-template", headers=login(client, "root")
    )

    assert response.status_code == 200
    assert response.json()["added"] == {"parameters": 0, "treatments": 0, "rules": 0, "modules": 0}
