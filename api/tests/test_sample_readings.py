"""The sample-readings command fills a plant with realistic history."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Reading
from app.scripts.sample_readings import fill
from tests.helpers import Tenant, login, make_tenant, with_template


@pytest.fixture
def acme(owner_db: Session) -> Tenant:
    tenant = make_tenant(owner_db, "acme")
    with_template(owner_db, tenant.company)
    return tenant


def test_fill_adds_balanced_readings_with_calculations(owner_db: Session, acme: Tenant) -> None:
    now = datetime.now(UTC)
    added = fill(owner_db, acme.plant_a, acme.manager.id, days=2, every=2, now=now)
    owner_db.commit()

    readings = owner_db.scalars(
        select(Reading).where(Reading.plant_id == acme.plant_a.id).order_by(Reading.recorded_at)
    ).all()
    assert added == len(readings) == 24
    assert all(r.recorded_at < now and r.created_by == acme.manager.id for r in readings)
    assert all(r.source == "manual" for r in readings)

    last = readings[-1]
    inputs, calc = last.input_values, last.calculated_values
    assert inputs["tr"] > inputs["ts"] > inputs["wbt"]
    assert inputs["pin"] > inputs["pout"]
    # Make-up balances evaporation + blowdown + drift, so both CoC methods roughly agree.
    assert calc["cocmis"] < 10
    assert 3 < calc["coc"] < 8
    # One backwash every 36 h, and trend KPIs are worked out from the series itself.
    assert sum(r.input_values["clean"] for r in readings) == 2
    assert calc["dprate"] is not None

    entry = owner_db.scalar(select(AuditLog).where(AuditLog.action == "readings.import"))
    assert entry is not None and entry.after is not None
    assert entry.after["readings"] == 24


def test_filled_history_shows_in_the_trend_charts(
    client: TestClient, owner_db: Session, acme: Tenant
) -> None:
    fill(owner_db, acme.plant_a, acme.manager.id, days=1, every=1)
    owner_db.commit()

    url = f"/api/v1/plants/{acme.plant_a.id}/modules/coc"
    view = client.get(url, headers=login(client, "acme-operator")).json()
    chart = next(w for w in view["widgets"] if w["title"] == "Blowdown Trend")
    assert len(chart["series"][0]["points"]) >= 23  # the oldest sits right at the 24 h edge
    assert owner_db.scalar(select(func.count()).select_from(Reading)) == 24
