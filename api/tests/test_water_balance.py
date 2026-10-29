"""The Water Balance module: the workbook's water balance with recycled water."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.engine.calculation import calculate
from app.templates.default import DEFAULT_TEMPLATE as T
from tests.helpers import Tenant, login, make_tenant, with_template
from tests.test_template import BASELINE, FORMULAS, SAMPLES, SETTINGS

SAMPLE_INPUTS = {p.key: p.sample for p in T.parameters if p.kind == "input" and p.active}


@pytest.fixture
def acme(owner_db: Session) -> Tenant:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    return tenant


def view(client: TestClient, tenant: Tenant, values: dict[str, Any]) -> Any:
    base = f"/api/v1/plants/{tenant.plant_a.id}"
    headers = login(client, "acme-manager")
    assert client.post(f"{base}/readings", json={"values": values}, headers=headers).status_code
    return client.get(f"{base}/modules/water_balance", headers=headers).json()


def numbers(values: dict[str, float | None]) -> dict[str, float]:
    return {k: v for k, v in values.items() if v is not None}


def test_sample_values_balance_like_the_workbook() -> None:
    v = numbers(calculate(SAMPLES, FORMULAS, BASELINE, None, SETTINGS))
    evap = v["evap"]

    assert v["totalin"] == pytest.approx(18.0)  # make-up 15 + recycled 3
    # Explained = evaporation + blowdown 3.4 + drift 0.2 + other loss 0.3 + storage 0
    assert v["explained"] == pytest.approx(evap + 3.9)
    assert v["unacc"] == pytest.approx(18.0 - evap - 3.9)
    assert v["wberr"] == pytest.approx(v["unacc"] / 18.0 * 100)
    # Expected make-up = evaporation + design blowdown 3.3 + drift 0.2 + design other 0.3
    # + design storage 0 - recycled 3
    assert v["expmu"] == pytest.approx(evap + 0.8)
    assert v["mudev"] == pytest.approx((15 - v["expmu"]) / v["expmu"] * 100)
    assert v["recshare"] == pytest.approx(3 / 18 * 100)
    assert v["discharge"] == pytest.approx(3.7)
    assert v["wbhealth"] == pytest.approx(100 - 3 * abs(v["wberr"]))
    assert v["excesscost"] == pytest.approx(v["excesswater"] * (45 + 18))


def test_without_recycling_the_balance_still_works() -> None:
    inputs = {**SAMPLES, "rwflow": None, "otherloss": None, "storage": None}
    v = calculate(inputs, FORMULAS, BASELINE, None, SETTINGS)
    assert v["totalin"] == pytest.approx(15.0)
    assert v["recshare"] == 0.0
    assert v["cocflow"] == pytest.approx(15 / 3.6)


def test_water_balance_screen_and_leak_prediction(client: TestClient, acme: Tenant) -> None:
    screen = view(client, acme, SAMPLE_INPUTS)
    assert screen["title"] == "Water Balance"
    diagram = next(w for w in screen["widgets"] if w["type"] == "system_diagram")
    assert set(diagram["named"]) == {"makeup", "recycled", "evaporation", "blowdown"}
    assert diagram["text"] == "Water flows"
    problems = next(w for w in screen["widgets"] if w["type"] == "predicted_problems")
    assert "WB-P01" not in [p["code"] for p in problems["problems"]]  # balance closes

    # 4 m³/h more make-up than the losses explain: about 18 % unaccounted -> leak suspected.
    leaking = view(client, acme, {"muflow": 19.0})
    problems = next(w for w in leaking["widgets"] if w["type"] == "predicted_problems")
    leak = next(p for p in problems["problems"] if p["code"] == "WB-P01")
    assert leak["priority"] == "high"
    cards = {c["tile"]["key"]: c for c in leaking["widgets"][0]["cards"]}
    assert cards["wberr"]["status"] == "bad"
