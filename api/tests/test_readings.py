"""Readings (autosave with merge), alerts, predicted problems and module screens."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.tenant import ALL_PLANTS, TenantContext, set_tenant_context
from app.models import OperatorProfile, Reading
from app.templates.default import PARAMETERS
from tests.helpers import Tenant, login, make_tenant, make_user, with_template

SAMPLE_INPUTS = {p.key: p.sample for p in PARAMETERS if p.kind == "input" and p.active}


@pytest.fixture
def acme(owner_db: Session) -> Tenant:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    return tenant


def base(tenant: Tenant) -> str:
    return f"/api/v1/plants/{tenant.plant_a.id}"


def save(client: TestClient, tenant: Tenant, user: str, values: dict[str, Any]) -> Any:
    return client.post(
        f"{base(tenant)}/readings", json={"values": values}, headers=login(client, user)
    )


def first_reading(client: TestClient, tenant: Tenant) -> Any:
    """A full set of sample values, as entered by the manager."""
    return save(client, tenant, "acme-manager", SAMPLE_INPUTS)


def module(client: TestClient, tenant: Tenant, key: str, user: str = "acme-operator") -> Any:
    return client.get(f"{base(tenant)}/modules/{key}", headers=login(client, user)).json()


def tiles(view: Any) -> dict[str, Any]:
    return {t["key"]: t for w in view["widgets"] for t in (w.get("tiles") or [])}


def alert_keys(client: TestClient, tenant: Tenant, user: str = "acme-operator") -> set[str]:
    body = client.get(f"{base(tenant)}/alerts", headers=login(client, user)).json()
    return {a["parameter_key"] for a in body["alerts"]}


# --- Saving ------------------------------------------------------------------------------------


def test_saving_stores_a_new_reading_with_calculated_values(
    client: TestClient, acme: Tenant
) -> None:
    response = first_reading(client, acme)

    assert response.status_code == 201, response.text
    reading = response.json()["reading"]
    assert reading["created_by"]["name"] == "Acme-Manager"
    assert reading["calculated_values"]["range"] == 8.0
    assert reading["calculated_values"]["resid"] == 1.0  # appr 5 - baseline 4
    assert reading["formula_versions"]["range"] == 1
    # Every plant setting used is stored with the reading (history stays explainable).
    assert reading["settings_used"]["clean_baseline_approach"] == 4.0
    assert reading["settings_used"]["design_flow"] == 1000.0


def test_changes_from_two_people_are_merged_not_overwritten(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    first_reading(client, acme)

    save(client, acme, "acme-operator", {"hard": 700})
    response = save(client, acme, "acme-manager", {"ph": 7.5})

    latest = response.json()["reading"]
    assert latest["input_values"]["hard"] == 700  # operator's change kept
    assert latest["input_values"]["ph"] == 7.5
    assert latest["changed_keys"] == ["ph"]
    assert len(owner_db.scalars(select(Reading)).all()) == 3  # every save is kept


def test_saving_the_same_value_again_creates_nothing(client: TestClient, acme: Tenant) -> None:
    first_reading(client, acme)

    response = save(client, acme, "acme-operator", {"hard": 650})

    assert response.status_code == 200
    assert response.json()["created"] is False


@pytest.mark.parametrize(
    ("values", "problem"),
    [
        ({"ghost": 1}, "Unknown or inactive parameter."),
        ({"range": 5}, "Calculated values cannot be entered."),
    ],
)
def test_invalid_values_are_rejected(
    client: TestClient, acme: Tenant, values: dict[str, Any], problem: str
) -> None:
    response = save(client, acme, "acme-operator", values)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["message"] == problem


def test_non_numbers_are_rejected(client: TestClient, acme: Tenant) -> None:
    assert save(client, acme, "acme-operator", {"hard": "lots"}).status_code == 422


def test_a_value_can_be_cleared(client: TestClient, acme: Tenant) -> None:
    first_reading(client, acme)

    latest = save(client, acme, "acme-operator", {"wbt": None}).json()["reading"]

    assert latest["input_values"]["wbt"] is None
    assert latest["calculated_values"]["appr"] is None  # depends on wbt


def test_history_keeps_old_calculations_after_a_formula_change(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    first_reading(client, acme)
    make_user(owner_db, "root", "super_admin")
    client.patch(
        f"/api/v1/companies/{acme.company_id}/parameters/range",
        json={"formula": "(tr - ts) * 2"},
        headers=login(client, "root"),
    )

    save(client, acme, "acme-operator", {"tr": 40})
    history = client.get(f"{base(acme)}/readings", headers=login(client, "acme-manager")).json()

    newest, oldest = history["items"][0], history["items"][-1]
    assert oldest["calculated_values"]["range"] == 8.0
    assert oldest["formula_versions"]["range"] == 1
    assert newest["calculated_values"]["range"] == 18.0
    assert newest["formula_versions"]["range"] == 2


def test_preview_calculates_without_storing(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    first_reading(client, acme)

    response = client.post(
        f"{base(acme)}/readings/preview",
        json={"values": {"hard": 900}},
        headers=login(client, "acme-operator"),
    )

    body = response.json()
    assert {t["key"]: t for t in body["tiles"]}["hard"]["status"] == "bad"
    assert "hard" in {a["parameter_key"] for a in body["alerts"]}
    assert len(owner_db.scalars(select(Reading)).all()) == 1


def test_latest_and_history_filters(client: TestClient, acme: Tenant) -> None:
    headers = login(client, "acme-manager")
    assert client.get(f"{base(acme)}/readings/latest", headers=headers).json() is None

    first_reading(client, acme)
    save(client, acme, "acme-operator", {"hard": 700})

    latest = client.get(f"{base(acme)}/readings/latest", headers=headers).json()
    page = client.get(f"{base(acme)}/readings?limit=1", headers=headers).json()
    future = client.get(f"{base(acme)}/readings?from=2999-01-01T00:00:00Z", headers=headers).json()
    assert latest["input_values"]["hard"] == 700
    assert page["total"] == 2 and len(page["items"]) == 1
    assert future["total"] == 0


# --- Permissions -------------------------------------------------------------------------------


def test_company_admin_can_view_but_not_enter_readings(client: TestClient, acme: Tenant) -> None:
    first_reading(client, acme)

    assert save(client, acme, "acme-admin", {"hard": 700}).status_code == 403
    view = module(client, acme, "water_chemistry", "acme-admin")
    assert view["can_edit_readings"] is False
    assert tiles(view)["hard"]["editable"] is False


def test_super_admin_never_sees_readings(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    first_reading(client, acme)
    make_user(owner_db, "root", "super_admin")
    headers = login(client, "root")

    for path in ("/readings/latest", "/readings", "/alerts", "/modules/water_chemistry"):
        assert client.get(base(acme) + path, headers=headers).status_code == 403, path


def test_operator_profile_can_block_editing_and_hide_modules(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    owner_db.add(
        OperatorProfile(
            user_id=acme.operator.id, plant_id=acme.plant_a.id, company_id=acme.company_id,
            visible_modules=["water_chemistry"], can_edit_readings=False,
        )
    )  # fmt: skip
    owner_db.commit()
    headers = login(client, "acme-operator")

    assert save(client, acme, "acme-operator", {"hard": 700}).status_code == 403
    keys = [m["key"] for m in client.get(f"{base(acme)}/modules", headers=headers).json()]
    assert keys == ["water_chemistry"]
    assert client.get(f"{base(acme)}/modules/filter", headers=headers).status_code == 404


def test_other_plants_are_not_found(client: TestClient, acme: Tenant) -> None:
    other = f"/api/v1/plants/{acme.plant_b.id}/readings"

    response = client.post(
        other, json={"values": {"hard": 1}}, headers=login(client, "acme-operator")
    )

    assert response.status_code == 404


# --- Alerts ------------------------------------------------------------------------------------


def test_alert_carries_severity_direction_modules_and_treatment(
    client: TestClient, acme: Tenant
) -> None:
    first_reading(client, acme)
    save(client, acme, "acme-operator", {"hard": 900})

    body = client.get(f"{base(acme)}/alerts", headers=login(client, "acme-operator")).json()

    hard = next(a for a in body["alerts"] if a["parameter_key"] == "hard")
    assert hard["severity"] == "high"  # 900 > warning max 800
    assert hard["direction"] == "high"
    assert hard["unit"] == "ppm"
    assert hard["cause"].startswith("Hard make-up water")
    assert hard["needs_review"] is True  # template text is a sample
    # Fouling (TH-P02) uses hardness and affects Thermal and Filter; scaling risk (COC-P03)
    # uses it too and is shown on CoC & Blowdown.
    assert set(hard["modules"]) == {"water_chemistry", "thermal", "filter", "coc"}
    assert body["alerts"][0]["severity"] == "high"  # most severe first
    assert body["reading"]["changed_keys"] == ["hard"]


def test_parameters_without_treatment_get_fallback_text(client: TestClient, acme: Tenant) -> None:
    first_reading(client, acme)
    save(client, acme, "acme-operator", {"tds": 2000})  # high side of the warning band

    body = client.get(f"{base(acme)}/alerts", headers=login(client, "acme-operator")).json()
    save(client, acme, "acme-operator", {"tds": 600})  # low: no "tds low" treatment in the template
    low = client.get(f"{base(acme)}/alerts", headers=login(client, "acme-operator")).json()

    assert next(a for a in body["alerts"] if a["parameter_key"] == "tds")["severity"] == "medium"
    tds_low = next(a for a in low["alerts"] if a["parameter_key"] == "tds")
    assert tds_low["direction"] == "low"
    assert "No guidance has been configured" in tds_low["cause"]


def test_manager_editing_a_limit_clears_the_alert(client: TestClient, acme: Tenant) -> None:
    first_reading(client, acme)
    assert "hard" in alert_keys(client, acme)  # sample hardness 650 > good max 600

    client.put(
        f"{base(acme)}/limits",
        json={"items": [{"parameter_key": "hard", "warn_min": 100, "good_min": 200,
                         "good_max": 700, "warn_max": 900}]},
        headers=login(client, "acme-manager"),
    )  # fmt: skip

    assert "hard" not in alert_keys(client, acme)


def test_manager_and_operator_see_the_same_alerts(client: TestClient, acme: Tenant) -> None:
    first_reading(client, acme)
    save(client, acme, "acme-operator", {"mic": 6000})

    assert alert_keys(client, acme, "acme-operator") == alert_keys(client, acme, "acme-manager")


# --- Modules -----------------------------------------------------------------------------------


def test_modules_list_comes_from_configuration(client: TestClient, acme: Tenant) -> None:
    response = client.get(f"{base(acme)}/modules", headers=login(client, "acme-operator"))

    assert [m["title"] for m in response.json()] == [
        "Input Parameters",
        "Side-Stream Filtration",
        "Thermal Efficiency",
        "CoC & Blowdown",
        "Water Balance",
    ]


def test_water_chemistry_shows_editable_inputs_and_calculated_values(
    client: TestClient, acme: Tenant
) -> None:
    first_reading(client, acme)

    view = module(client, acme, "water_chemistry")

    assert [w["title"] for w in view["widgets"]] == [
        "Chemistry", "Thermal", "Side-stream filter", "Make-up, blowdown & dosing",
        "Water balance", "Indication", "Calculated values",
    ]  # fmt: skip
    indication = next(w for w in view["widgets"] if w["title"] == "Indication")
    assert [t["key"] for t in indication["tiles"]] == ["clean", "valve", "sspump", "bdvalve", "bwt"]
    assert indication["switches"] == ["clean", "valve", "sspump", "bdvalve"]
    filter_row = next(w for w in view["widgets"] if w["title"] == "Side-stream filter")
    assert not {"clean", "bwt", "valve", "sspump"} & {t["key"] for t in filter_row["tiles"]}
    all_tiles = tiles(view)
    assert all_tiles["hard"] == all_tiles["hard"] | {
        "value": 650.0,
        "status": "warn",
        "editable": True,
    }
    assert all_tiles["lsi"]["editable"] is False
    assert view["reading"]["created_by"]["name"] == "Acme-Manager"


def test_measured_dp_and_calculated_fan_power(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    make_user(owner_db, "root", "super_admin")
    root_headers = login(client, "root")
    config = f"/api/v1/companies/{acme.company_id}/parameters"
    assert client.patch(f"{config}/dp", json={"kind": "input"}, headers=root_headers).is_success
    assert client.patch(
        f"{config}/fan", json={"kind": "calculated"}, headers=root_headers
    ).is_success
    first_reading(client, acme)
    response = save(
        client, acme, "acme-operator", {"dp": 0.9, "fanv": 415, "fani": 115, "fanpf": 0.85}
    )
    assert response.status_code == 201, response.text

    view = module(client, acme, "water_chemistry")
    rows = {w["title"]: [t["key"] for t in w["tiles"] or []] for w in view["widgets"]}
    # dP is typed in with the filter inputs, no longer listed under calculated values.
    assert "dp" in rows["Side-stream filter"] and "dp" not in rows["Calculated values"]
    # Fan power moves from the thermal inputs to the calculated values.
    assert {"fanv", "fani", "fanpf"} <= set(rows["Thermal"]) and "fan" not in rows["Thermal"]
    assert "fan" in rows["Calculated values"]
    all_tiles = tiles(view)
    assert all_tiles["dp"]["value"] == 0.9 and all_tiles["dp"]["editable"] is True
    assert all_tiles["fan"]["value"] == pytest.approx(70.26, abs=0.01)
    # Typing pin/pout no longer changes the measured dP.
    save(client, acme, "acme-operator", {"pin": 3.0})
    assert tiles(module(client, acme, "water_chemistry"))["dp"]["value"] == 0.9


def test_filter_and_thermal_update_when_chemistry_changes(client: TestClient, acme: Tenant) -> None:
    first_reading(client, acme)
    thermal_before = module(client, acme, "thermal")
    filter_before = module(client, acme, "filter")

    # LSI and hardness are already off with the samples; alkalinity adds a third sign.
    save(client, acme, "acme-operator", {"tds": 2300, "hard": 900, "alk": 500})

    thermal = module(client, acme, "thermal")
    filter_ = module(client, acme, "filter")
    th_before = next(w for w in thermal_before["widgets"] if w["type"] == "predicted_problems")
    th_after = next(w for w in thermal["widgets"] if w["type"] == "predicted_problems")
    flt_before = next(w for w in filter_before["widgets"] if w["type"] == "predicted_problems")
    flt_after = next(w for w in filter_["widgets"] if w["type"] == "predicted_problems")

    assert [p["code"] for p in th_before["problems"]] == ["TH-P02"]
    assert th_after["problems"][0]["probability"] > th_before["problems"][0]["probability"]
    assert flt_before["problems"] == []
    assert [p["code"] for p in flt_after["problems"]] == ["FLT-P03"]  # TDS now out of range


def test_predictions_need_data(client: TestClient, acme: Tenant) -> None:
    view = module(client, acme, "thermal")  # no readings yet

    problems = next(w for w in view["widgets"] if w["type"] == "predicted_problems")
    assert problems["problems"] == []
    assert problems["insufficient_rules"] == [f"TH-P0{i}" for i in range(1, 7)]


def test_inactive_parameters_degrade_to_insufficient_data(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    first_reading(client, acme)
    make_user(owner_db, "root", "super_admin")
    client.patch(
        f"/api/v1/companies/{acme.company_id}/parameters/tssout",
        json={"is_active": False},
        headers=login(client, "root"),
    )

    view = module(client, acme, "filter")

    assert tiles(view)["tssout"]["insufficient_data"] is True
    assert tiles(view)["dp"]["value"] == pytest.approx(0.6)  # the rest still works


def test_new_calculation_appears_in_a_module_without_code_changes(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    first_reading(client, acme)
    make_user(owner_db, "root", "super_admin")
    root = login(client, "root")
    company = f"/api/v1/companies/{acme.company_id}"
    client.post(f"{company}/parameters", headers=root, json={
        "key": "cycles", "label": "Cycles of concentration", "group_key": "chemistry",
        "kind": "calculated", "formula": "cond / 300", "precision": 1,
    })  # fmt: skip
    layout = {"widgets": [{"type": "value_tiles", "params": ["dp", "rem", "bw", "cycles"]}]}
    client.patch(f"{company}/modules/filter", json={"layout": layout}, headers=root)

    cycles = tiles(module(client, acme, "filter"))["cycles"]

    assert cycles["label"] == "Cycles of concentration"
    assert cycles["value"] == 8.0  # 2400 / 300, calculated from the latest inputs


# --- Database layer ----------------------------------------------------------------------------


def test_readings_cannot_be_changed_or_deleted_even_with_raw_sql(
    client: TestClient, acme: Tenant, app_engine: Engine
) -> None:
    first_reading(client, acme)
    context = TenantContext(
        user_id=acme.manager.id, company_id=acme.company_id, plant_ids=ALL_PLANTS
    )

    for sql in ("UPDATE readings SET source = 'x'", "DELETE FROM readings"):
        with Session(app_engine) as session:
            set_tenant_context(session, context)
            with pytest.raises(ProgrammingError, match="permission denied"):
                session.execute(text(sql))


def test_rls_hides_readings_from_other_companies_and_the_platform(
    client: TestClient, acme: Tenant, app_engine: Engine, owner_db: Session
) -> None:
    first_reading(client, acme)
    beta = make_tenant(owner_db, "beta")

    for context in (
        TenantContext(user_id=beta.admin.id, company_id=beta.company_id, plant_ids=ALL_PLANTS),
        TenantContext(user_id=beta.admin.id, platform=True),
    ):
        with Session(app_engine) as session:
            set_tenant_context(session, context)
            assert session.execute(text("SELECT count(*) FROM readings")).scalar() == 0


def test_trend_kpis_and_predictions_use_the_plant_history(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    # 12 hours ago the filter ΔP was 0.3 bar; now it is 0.6 bar, so the filter is loading at
    # 0.6 bar/day and normal loading (FLT-P01) is predicted with a time to clean.
    earlier = {**SAMPLE_INPUTS, "pin": 2.1}
    owner_db.add(
        Reading(
            company_id=acme.company_id, plant_id=acme.plant_a.id,
            recorded_at=datetime.now(UTC) - timedelta(hours=12), source="seed",
            input_values=earlier, calculated_values={"dp": 0.3}, formula_versions={},
        )
    )  # fmt: skip
    owner_db.commit()
    first_reading(client, acme)  # today's full set (ΔP 0.6)

    view = module(client, acme, "filter")
    kpis = tiles(view)
    problems = next(w for w in view["widgets"] if w["type"] == "predicted_problems")

    assert kpis["dprate"]["value"] == pytest.approx(0.6, rel=0.01)
    assert "FLT-P01" in [p["code"] for p in problems["problems"]]
    assert "FLT-P05" in problems["insufficient_rules"]  # no cleaning recorded yet


def test_notification_includes_predicted_problems_unless_hidden(
    client: TestClient, acme: Tenant, owner_db: Session
) -> None:
    first_reading(client, acme)  # sample hardness 650 > 600: fouling risk (TH-P02)
    body = client.get(f"{base(acme)}/alerts", headers=login(client, "acme-operator")).json()
    assert "TH-P02" in [p["code"] for p in body["problems"]]

    owner_db.add(
        OperatorProfile(
            user_id=acme.operator.id, plant_id=acme.plant_a.id, company_id=acme.company_id,
            show_alerts=False,
        )
    )  # fmt: skip
    owner_db.commit()
    hidden = client.get(f"{base(acme)}/alerts", headers=login(client, "acme-operator")).json()
    assert hidden["alerts"] == [] and hidden["problems"] == []
