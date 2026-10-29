"""Fill a plant with realistic readings for the past days, e.g. for a demo company, so trend
charts and trend KPIs have history. Works in every environment, including production.

    cd api && .venv/bin/python -m app.scripts.sample_readings --company "Demo Co" --plant "Unit 1"

Options: --days 7 (how far back), --every 1 (hours between readings), --user <username> (who the
readings are saved by; default: the plant's manager), --yes (no confirmation prompt).

Values start from the plant's latest reading (or the parameters' sample values) and move like a
real plant: daily wet-bulb swing, filter ΔP rising between backwashes, make-up and blowdown flows
that balance with evaporation, conductivity that follows cycles of concentration. Calculated
values use the company's current formulas, exactly like a normal save. The import is recorded in
the audit log. Use it only for demo or test plants, never for a customer's real plant.
"""

import argparse
import math
import random
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.engine.calculation import calculate, history_hours
from app.engine.history import History
from app.models import Company, Parameter, Plant, Reading, RoleAssignment, User
from app.scripts.seed_dev import owner_url
from app.services.audit import record_for
from app.services.config_common import active_parameters, parsed_formulas
from app.services.limits import plant_setting, plant_settings_values
from app.services.plant_state import BASELINE_SETTING

SWITCHES = {"clean": 0.0, "valve": 0.0, "sspump": 1.0, "bdvalve": 1.0}
CLEAN_EVERY_HOURS = 36  # one backwash about every day and a half
DRIFT = 0.2  # m³/h, the template's default drift loss


def _wave(hours: float, period: float, phase: float = 0.0) -> float:
    return math.sin(2 * math.pi * (hours / period) + phase)


def generate_inputs(
    base: Mapping[str, float | None],
    params: Mapping[str, Parameter],
    hours: float,
    rng: random.Random,
    every: float = 1.0,
    drift: dict[str, float] | None = None,
) -> dict[str, float | None]:
    """One set of input values `hours` after the start of the series. `drift` holds each
    parameter's slowly wandering offset, so values change smoothly from hour to hour."""
    values: dict[str, float | None] = {}
    drift = {} if drift is None else drift
    for key in (k for k, p in params.items() if p.kind == "input"):
        start = base.get(key)
        if key in SWITCHES:
            values[key] = SWITCHES[key]
        elif start is None:
            values[key] = None
        else:  # a slow daily wave plus a little noise around the starting value
            phase = sum(map(ord, key)) % 7  # each parameter peaks at its own time of day
            drift[key] = 0.85 * drift.get(key, 0.0) + 0.15 * rng.gauss(0, 1)
            wave = 0.03 * _wave(hours, 24, phase) + 0.03 * drift[key]
            values[key] = start * (1 + wave)

    def has(*keys: str) -> bool:
        return all(values.get(k) is not None for k in keys)

    # Thermal: wet-bulb swings ±2 °C a day; supply and return follow it.
    if has("wbt", "ts", "tr") and base.get("wbt") is not None:
        wbt = float(base["wbt"] or 0) + 2.0 * _wave(hours, 24, -math.pi / 2) + 0.2 * rng.gauss(0, 1)
        drift["_approach"] = 0.85 * drift.get("_approach", 0.0) + 0.15 * rng.gauss(0, 1)
        approach = float((base["ts"] or 0) - (base["wbt"] or 0)) + 0.6 * drift["_approach"]
        cooling_range = float((base["tr"] or 0) - (base["ts"] or 0)) * (1 + 0.04 * _wave(hours, 24))
        values["wbt"], values["ts"] = wbt, wbt + approach
        values["tr"] = wbt + approach + cooling_range

    # Filter: ΔP climbs from clean to loaded between backwashes; the backwash flag is set once.
    since_clean = hours % CLEAN_EVERY_HOURS
    if "clean" in values:
        values["clean"] = 1.0 if since_clean < every else 0.0
    dp = 0.25 + 0.45 * (since_clean / CLEAN_EVERY_HOURS) + 0.02 * rng.gauss(0, 1)
    if params.get("dp") is not None and params["dp"].kind == "input":
        values["dp"] = dp
    if has("pin", "pout"):
        values["pin"] = float(values["pout"] or 0) + dp
    if has("tin", "tout"):
        values["tout"] = min(float(values["tout"] or 0), float(values["tin"] or 0) * 0.5)

    # Water balance: make-up + recycled = evaporation + blowdown + drift + other loss + storage
    # change (with a small unaccounted part); conductivity = CoC x make-up EC.
    if has("flow", "ts", "tr", "bdflow", "muflow"):
        mean_t = (float(values["ts"] or 0) + float(values["tr"] or 0)) / 2
        heat = (
            1.163
            * float(values["flow"] or 0)
            * (float(values["tr"] or 0) - float(values["ts"] or 0))
        )
        evaporation = heat * 3600 / ((2501 - 2.361 * mean_t) * 1000)
        bd = float(values["bdflow"] or 0)
        other = float(values.get("otherloss") or 0)
        recycled = float(values.get("rwflow") or 0)
        if "storage" in values:
            values["storage"] = 0.2 * _wave(hours, 24)  # basin level drifts a little each day
        storage = float(values.get("storage") or 0)
        losses = evaporation + bd + DRIFT + other + storage
        values["muflow"] = max(0.0, losses * (1 + 0.01 * rng.gauss(0, 1)) - recycled)
        if has("mucond", "cond"):
            coc = (float(values["muflow"] or 0) + recycled) / (bd + DRIFT + other)
            values["cond"] = float(values["mucond"] or 0) * coc * (1 + 0.005 * rng.gauss(0, 1))

    return {
        k: (round(v, params[k].precision) if isinstance(v, float) else v) for k, v in values.items()
    }


def fill(
    db: Session,
    plant: Plant,
    user_id: Any,
    days: float,
    every: float,
    now: datetime | None = None,
) -> int:
    """Add the readings (does not commit). Returns how many were added."""
    now = now or datetime.now(UTC)
    params = active_parameters(db, plant.company_id)
    latest = db.scalar(
        select(Reading).where(Reading.plant_id == plant.id).order_by(Reading.recorded_at.desc())
    )
    base: dict[str, float | None] = {
        k: p.sample_value for k, p in params.items() if p.kind == "input"
    }
    if latest is not None:
        base.update({k: v for k, v in latest.input_values.items() if v is not None and k in base})

    formulas = parsed_formulas(params.values())
    lookback = history_hours(formulas.values())
    baseline = plant_setting(db, plant, BASELINE_SETTING)
    settings = plant_settings_values(db, plant)
    rng = random.Random(str(plant.id))  # noqa: S311  # sample values, not security
    start = now - timedelta(days=days)
    steps = int(days * 24 / every)
    points: list[tuple[datetime, dict[str, Any]]] = []
    drift: dict[str, float] = {}
    for i in range(steps):
        t = start + timedelta(hours=i * every)
        inputs = generate_inputs(base, params, i * every, rng, every, drift)
        recent = [p for p in points if p[0] >= t - timedelta(hours=lookback)] if lookback else []
        history = History(now=t, points=recent) if lookback else None
        calculated = calculate(inputs, formulas, baseline, history, settings)
        points.append((t, {**inputs, **calculated}))
        db.add(
            Reading(
                company_id=plant.company_id, plant_id=plant.id, recorded_at=t,
                created_by=user_id, source="manual", input_values=inputs,
                calculated_values=calculated,
                formula_versions={k: params[k].formula_version for k in formulas},
                settings_used={**settings, BASELINE_SETTING: baseline},
                changed_keys=sorted(k for k, v in inputs.items() if v is not None),
            )
        )  # fmt: skip
    record_for(
        db, user_id, "readings.import", "plant", plant.id, company_id=plant.company_id,
        after={"readings": steps, "days": days, "every_hours": every},
    )  # fmt: skip
    return steps


def _one(items: list[Any], what: str, typed: str, name: Any) -> Any:
    """The single match for a (part of a) name, or exit with the choices."""
    if len(items) != 1:
        found = ", ".join(name(i) for i in items) or "none"
        sys.exit(f"{what} '{typed}' must match exactly one; matches: {found}.")
    return items[0]


def _find_plant(db: Session, company_name: str, plant_name: str) -> Plant:
    """Names may be given in part, any case (e.g. --plant "unit 1")."""
    companies = list(db.scalars(select(Company).where(Company.name.ilike(f"%{company_name}%"))))
    company: Company = _one(companies, "Company", company_name, lambda c: c.name)
    plants = list(
        db.scalars(
            select(Plant).where(Plant.company_id == company.id, Plant.name.ilike(f"%{plant_name}%"))
        )
    )
    plant: Plant = _one(plants, "Plant", plant_name, lambda p: p.name)
    return plant


def _find_user(db: Session, plant: Plant, username: str | None) -> User:
    if username:
        user = db.scalar(select(User).where(User.username == username.lower()))
    else:  # the plant's active manager
        user = db.scalar(
            select(User)
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .where(
                RoleAssignment.plant_id == plant.id,
                RoleAssignment.role_key == "manager",
                User.is_active.is_(True),
            )
        )
    if user is None:
        sys.exit("No user found to save the readings as; pass --user <username>.")
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--company", required=True)
    parser.add_argument("--plant", required=True)
    parser.add_argument("--days", type=float, default=7)
    parser.add_argument("--every", type=float, default=1, help="hours between readings")
    parser.add_argument("--user", help="username the readings are saved by")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = parser.parse_args()
    if not 0 < args.days <= 90 or not 0.25 <= args.every <= 24:
        sys.exit("--days must be 0-90 and --every 0.25-24 hours.")

    with Session(create_engine(owner_url())) as db:
        plant = _find_plant(db, args.company, args.plant)
        user = _find_user(db, plant, args.user)
        count = int(args.days * 24 / args.every)
        print(f"{count} readings for '{plant.name}', last {args.days:g} days, every "
              f"{args.every:g} h, saved by {user.full_name} ({user.username}).")  # fmt: skip
        if not args.yes and input("Type YES to continue: ").strip() != "YES":
            sys.exit("Nothing was added.")
        fill(db, plant, user.id, args.days, args.every)
        db.commit()
    print(f"Added {count} readings.")


if __name__ == "__main__":
    main()
