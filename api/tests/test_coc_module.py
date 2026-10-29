"""The CoC & Blowdown module: its KPIs, screen pieces (KPI cards, diagram, charts with time
ranges, problems table, recommended actions, quick links) and rule priority/benefit/ETA."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.engine.calculation import RuleContext, calculate, evaluate_rule, parse_rule
from app.engine.status import Status
from app.models import OperatorProfile, Reading
from app.templates.default import DEFAULT_TEMPLATE as T
from tests.helpers import Tenant, login, make_tenant, make_user, with_template
from tests.test_template import BASELINE, FORMULAS, SAMPLES, SETTINGS

SAMPLE_INPUTS = {p.key: p.sample for p in T.parameters if p.kind == "input" and p.active}


@pytest.fixture
def acme(owner_db: Session) -> Tenant:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    make_user(owner_db, "root", "super_admin")
    return tenant


def base(tenant: Tenant) -> str:
    return f"/api/v1/plants/{tenant.plant_a.id}"


def save(client: TestClient, tenant: Tenant, values: dict[str, Any]) -> None:
    headers = login(client, "acme-manager")
    response = client.post(f"{base(tenant)}/readings", json={"values": values}, headers=headers)
    assert response.status_code in (200, 201), response.text


def coc_view(client: TestClient, tenant: Tenant, user: str = "acme-operator") -> Any:
    response = client.get(f"{base(tenant)}/modules/coc", headers=login(client, user))
    assert response.status_code == 200, response.text
    return response.json()


def widget(view: Any, kind: str, title: str | None = None) -> Any:
    return next(
        w for w in view["widgets"] if w["type"] == kind and (title is None or w["title"] == title)
    )


# --- Formulas (sample values) ------------------------------------------------------------------


def test_sample_values_give_the_expected_coc_kpis() -> None:
    v = calculate(SAMPLES, FORMULAS, BASELINE, None, SETTINGS)

    assert v["coc"] == pytest.approx(5.0)  # 2400 / 480
    # Heat 9304 kW, h_fg = 2501 - 2.361 x 35 = 2418.4 kJ/kg → 13.85 m³/h evaporated.
    assert v["evap"] == pytest.approx(13.850, abs=1e-3)
    assert v["bdreq"] == pytest.approx(13.850 / 4 - 0.2, abs=1e-3)  # E / (CoC - 1) - drift
    assert v["bddev"] == pytest.approx((3.4 - 3.2625) / 3.2625 * 100, abs=0.1)
    # (make-up 15 + recycled 3) / (blowdown 3.4 + drift 0.2 + other loss 0.3)
    assert v["cocflow"] == pytest.approx(18 / 3.9)
    assert v["cocmis"] == pytest.approx(abs(5.0 - 18 / 3.9) / 5.0 * 100)
    assert v["condsp"] == pytest.approx(2400.0)  # make-up EC x target CoC
    assert v["condvsp"] == pytest.approx(0.0)
    assert v["bdlower"] == pytest.approx((4.7 - 3.4) / 4.7 * 100)
    assert v["mulower"] == pytest.approx((21.5 - 15) / 21.5 * 100)
    assert v["watersaved"] == pytest.approx(156.0)  # (21.5 - 15) x 24 h, no history yet
    assert v["costsaved"] == pytest.approx(156.0 * 45)
    assert v["chemvt"] == pytest.approx((2.35 - 2.6) / 2.6 * 100)


def test_required_blowdown_is_never_negative() -> None:
    v = calculate({**SAMPLES, "flow": 1.0}, FORMULAS, BASELINE, None, SETTINGS)
    assert v["bdreq"] == 0.0


def test_high_and_low_helpers_follow_the_status_direction() -> None:
    statuses = {"a": Status("warn", "high"), "b": Status("bad", "low"), "c": Status("good")}
    context = RuleContext({"a": 1.0, "b": 1.0, "c": 1.0}, statuses)

    def run(source: str) -> object:
        return evaluate_rule(parse_rule(source), context)

    assert run("high('a')") is True and run("low('a')") is False
    assert run("low('b')") is True and run("high('b')") is False
    assert run("high('c') or low('c')") is False


def test_coc_rules_have_a_priority_and_targets_are_left_to_the_manager() -> None:
    for rule in T.rules:
        assert rule.priority in ("high", "medium", "low"), rule.code
        assert rule.eta is None, rule.code  # ETA is not shown (owner decision)
    # CoC and ORP ranges are set per plant by the manager, not shipped as defaults.
    limits = {p.key: p.limits for p in T.parameters}
    assert limits["coc"] is None and limits["orp"] is None


# --- Module screen -----------------------------------------------------------------------------


def test_coc_module_screen_has_every_piece(client: TestClient, acme: Tenant) -> None:
    save(client, acme, SAMPLE_INPUTS)
    view = coc_view(client, acme)

    assert view["title"] == "CoC & Blowdown"
    assert [w["type"] for w in view["widgets"]] == [
        "kpi_cards", "system_diagram", "kpi_cards", "trend_chart", "trend_chart", "trend_chart",
        "trend_chart", "predicted_problems", "recommended_actions", "quick_links",
    ]  # fmt: skip

    cards = {c["tile"]["key"]: c for c in view["widgets"][0]["cards"]}
    # Targets are the plant's limits: conductivity has default limits, CoC has none yet.
    assert (cards["cond"]["target_min"], cards["cond"]["target_max"]) == (1200.0, 2800.0)
    assert cards["cond"]["status"] == "good"
    assert cards["coc"]["target_min"] is None and cards["coc"]["status"] == "na"
    assert cards["costsaved"]["delta"] == pytest.approx(30.2, abs=0.1)  # % less make-up
    assert cards["costsaved"]["caption"] == "vs baseline"

    benefits = widget(view, "kpi_cards", "Customer Benefits Today")
    assert benefits["style"] == "benefit"
    in_range = {c["tile"]["key"]: c["in_range"] for c in benefits["cards"]}
    assert in_range["coc"] is None  # no target set yet

    diagram = widget(view, "system_diagram")
    assert diagram["named"]["makeup"]["value"] == 15.0
    assert diagram["named"]["blowdown"]["value"] == 3.4
    assert [t["key"] for t in diagram["tiles"]] == ["cond", "ph", "orp", "ts"]

    chart = widget(view, "trend_chart", "Blowdown Trend")
    assert chart["ranges"] == [6, 24, 168, 720] and chart["hours"] == 24
    assert chart["combine"] is True
    assert [s["key"] for s in chart["series"]] == ["bdflow", "bdreq"]

    links = widget(view, "quick_links")["links"]
    assert links[0] == {"label": "Adjust blowdown setpoint", "target": "limits"}


def test_excessive_blowdown_shows_priority_and_benefit(client: TestClient, acme: Tenant) -> None:
    save(client, acme, {**SAMPLE_INPUTS, "bdflow": 5.0})  # 53 % above the required 3.26
    view = coc_view(client, acme)

    problems = widget(view, "predicted_problems")
    assert problems["style"] == "table"
    excessive = next(p for p in problems["problems"] if p["code"] == "COC-P01")
    assert excessive["priority"] == "high"
    assert excessive["eta_hours"] is None  # no ETA in the template
    assert excessive["benefit"] == "Maintain optimal CoC · save water"

    actions = widget(view, "recommended_actions")["problems"]
    assert "COC-P01" in [a["code"] for a in actions]


def test_rising_conductivity_is_predicted_from_the_trend(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    # 4 hours ago conductivity was 2300; now 2420: rising, just above the 2400 setpoint.
    owner_db.add(
        Reading(
            company_id=acme.company_id, plant_id=acme.plant_a.id,
            recorded_at=datetime.now(UTC) - timedelta(hours=4), source="seed",
            input_values={**SAMPLE_INPUTS, "cond": 2300}, calculated_values={},
            formula_versions={},
        )
    )  # fmt: skip
    owner_db.commit()
    save(client, acme, {**SAMPLE_INPUTS, "cond": 2420})

    problems = widget(coc_view(client, acme), "predicted_problems")["problems"]
    assert "COC-P02" in [p["code"] for p in problems]


def test_missing_makeup_conductivity_degrades_to_insufficient_data(
    client: TestClient, acme: Tenant
) -> None:
    save(client, acme, {k: v for k, v in SAMPLE_INPUTS.items() if k != "mucond"})
    view = coc_view(client, acme)

    cards = {c["tile"]["key"]: c for c in view["widgets"][0]["cards"]}
    assert cards["coc"]["tile"]["value"] is None and cards["coc"]["status"] == "na"
    assert "COC-P06" in widget(view, "predicted_problems")["insufficient_rules"]


# --- Trend time ranges -------------------------------------------------------------------------


def test_trend_endpoint_returns_other_time_ranges(client: TestClient, acme: Tenant) -> None:
    save(client, acme, SAMPLE_INPUTS)
    headers = login(client, "acme-operator")
    url = f"{base(acme)}/modules/coc/trend"

    response = client.get(url, params={"widget": 4, "hours": 168}, headers=headers)
    assert response.status_code == 200
    assert [s["key"] for s in response.json()] == ["bdflow", "bdreq"]

    # Only the chart's own ranges, and only trend charts.
    assert client.get(url, params={"widget": 4, "hours": 48}, headers=headers).status_code == 422
    assert client.get(url, params={"widget": 0, "hours": 24}, headers=headers).status_code == 404


def test_trend_endpoint_respects_module_visibility(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    owner_db.add(
        OperatorProfile(
            user_id=acme.operator.id, plant_id=acme.plant_a.id, company_id=acme.company_id,
            visible_modules=["water_chemistry"],
        )
    )  # fmt: skip
    owner_db.commit()
    response = client.get(
        f"{base(acme)}/modules/coc/trend",
        params={"widget": 3, "hours": 24},
        headers=login(client, "acme-operator"),
    )
    assert response.status_code == 404


# --- Rule configuration ------------------------------------------------------------------------


def test_rules_store_priority_benefit_and_validated_eta(client: TestClient, acme: Tenant) -> None:
    headers = login(client, "root")
    url = f"/api/v1/companies/{acme.company_id}/rules"
    body = {
        "code": "X-P01",
        "title": "High conductivity soon",
        "condition_expr": "cond > 2000",
        "probability_expr": "50",
        "priority": "low",
        "benefit_text": "Avoid scale",
        "eta_expr": "(2800 - cond) / 10",
    }

    created = client.post(url, json=body, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json() | {"priority": "low", "eta_expr": "(2800 - cond) / 10"} == created.json()

    bad = client.post(url, json={**body, "code": "X-P02", "eta_expr": "nope + 1"}, headers=headers)
    assert bad.status_code == 422

    cleared = client.patch(f"{url}/X-P01", json={"eta_expr": ""}, headers=headers)
    assert cleared.json()["eta_expr"] is None

    test = client.post(
        f"{url}/test",
        json={"condition_expr": "cond > 2000", "eta_expr": "(2800 - cond) / 10",
              "values": {"cond": 2400}},
        headers=headers,
    )  # fmt: skip
    assert test.json()["eta_hours"] == pytest.approx(40.0)


def test_template_update_refreshes_rule_priority(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    headers = login(client, "root")
    url = f"/api/v1/companies/{acme.company_id}"
    client.patch(f"{url}/rules/COC-P01", json={"priority": "low"}, headers=headers)

    client.post(f"{url}/apply-template?update_existing=true", json={}, headers=headers)

    rules = {r["code"]: r for r in client.get(f"{url}/rules", headers=headers).json()}
    assert rules["COC-P01"]["priority"] == "high"


def test_new_company_gets_the_coc_settings(owner_db: Session) -> None:
    tenant = make_tenant(owner_db, "beta")
    with_template(owner_db, tenant.company)
    defaults = tenant.company.settings["plant_setting_defaults"]
    assert defaults["target_coc"] == 5.0 and defaults["water_cost"] == 45.0


def test_kpi_card_targets_follow_the_managers_limits(client: TestClient, acme: Tenant) -> None:
    save(client, acme, SAMPLE_INPUTS)
    headers = login(client, "acme-manager")
    limits = {"parameter_key": "coc", "warn_min": 3, "good_min": 4, "good_max": 6, "warn_max": 7}
    response = client.put(f"{base(acme)}/limits", json={"items": [limits]}, headers=headers)
    assert response.status_code == 200, response.text

    view = coc_view(client, acme)
    coc = next(c for c in view["widgets"][0]["cards"] if c["tile"]["key"] == "coc")
    assert (coc["target_min"], coc["target_max"], coc["status"]) == (4.0, 6.0, "good")
    benefits = widget(view, "kpi_cards", "Customer Benefits Today")
    assert next(c for c in benefits["cards"] if c["tile"]["key"] == "coc")["in_range"] is True
