"""Saving and reading plant readings.

A save sends only the changed fields. The server merges them onto the latest reading's inputs
and stores a NEW reading (readings are never updated), so two people changing different fields
at the same time don't overwrite each other; for the same field, the last save wins.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import PermissionDeniedError, ValidationFailedError
from app.engine.calculation import calculate, history_hours
from app.models import OperatorProfile, Parameter, Plant, Reading, User
from app.schemas.common import PageParams
from app.schemas.readings import Person, Preview, ReadingOut, ReadingSummary
from app.services.config_common import active_parameters, parsed_formulas
from app.services.limits import plant_setting, plant_settings_values
from app.services.plant_state import (
    BASELINE_SETTING,
    alerts,
    build_state,
    load_history,
    predicted_problems,
)
from app.services.plants import get_plant_in_scope


def operator_profile(
    db: Session, principal: Principal, plant_id: uuid.UUID
) -> OperatorProfile | None:
    """The manager's restrictions for this user at this plant. No row = no restrictions."""
    return db.get(OperatorProfile, (principal.user_id, plant_id))


def can_edit_readings(db: Session, principal: Principal, plant_id: uuid.UUID) -> bool:
    if not principal.has("readings.write"):
        return False
    profile = operator_profile(db, principal, plant_id)
    return profile is None or profile.can_edit_readings


def latest_reading(db: Session, plant_id: uuid.UUID) -> Reading | None:
    return db.scalar(
        select(Reading)
        .where(Reading.plant_id == plant_id)
        .order_by(Reading.recorded_at.desc(), Reading.id.desc())
        .limit(1)
    )


def _check_changes(params: dict[str, Parameter], changes: dict[str, float | None]) -> None:
    problems = []
    for key in changes:
        p = params.get(key)
        if p is None:
            problems.append({"field": key, "message": "Unknown or inactive parameter."})
        elif p.kind != "input":
            problems.append({"field": key, "message": "Calculated values cannot be entered."})
    if problems:
        raise ValidationFailedError("Some values cannot be saved.", problems)


def _merged_inputs(
    db: Session, plant: Plant, params: dict[str, Parameter], changes: dict[str, float | None]
) -> tuple[dict[str, float | None], Reading | None]:
    latest = latest_reading(db, plant.id)
    previous = latest.input_values if latest else {}
    merged = {key: previous.get(key) for key, p in params.items() if p.kind == "input"}
    merged.update(changes)
    return merged, latest


def save_reading(
    db: Session, principal: Principal, plant_id: uuid.UUID, changes: dict[str, float | None]
) -> tuple[Reading, bool]:
    """Store a new reading with the changes applied. Returns (reading, created).
    If nothing actually changed, no row is added and the latest reading is returned."""
    plant = get_plant_in_scope(db, principal, plant_id)
    if not can_edit_readings(db, principal, plant.id):
        raise PermissionDeniedError("You are not allowed to enter readings for this plant.")
    params = active_parameters(db, plant.company_id)
    _check_changes(params, changes)
    merged, latest = _merged_inputs(db, plant, params, changes)

    previous = latest.input_values if latest else {}
    changed = sorted(k for k, v in changes.items() if previous.get(k) != v)
    if latest is not None and not changed:
        return latest, False

    formulas = parsed_formulas(params.values())
    base = plant_setting(db, plant, BASELINE_SETTING)
    now = datetime.now(UTC)
    history = load_history(db, plant, history_hours(formulas.values()), now)
    settings = plant_settings_values(db, plant)
    reading = Reading(
        company_id=plant.company_id,
        plant_id=plant.id,
        recorded_at=now,
        created_by=principal.user_id,
        source="manual",
        input_values=merged,
        calculated_values=calculate(merged, formulas, base, history, settings),
        formula_versions={k: params[k].formula_version for k in formulas},
        settings_used={**settings, BASELINE_SETTING: base},
        changed_keys=changed,
    )
    db.add(reading)
    db.commit()
    return reading, True


def preview(
    db: Session, principal: Principal, plant_id: uuid.UUID, changes: dict[str, float | None]
) -> Preview:
    """What the screen would show with these changes. Nothing is stored or shown to others."""
    plant = get_plant_in_scope(db, principal, plant_id)
    if not can_edit_readings(db, principal, plant.id):
        raise PermissionDeniedError("You are not allowed to enter readings for this plant.")
    params = active_parameters(db, plant.company_id)
    _check_changes(params, changes)
    merged, _ = _merged_inputs(db, plant, params, changes)
    state = build_state(db, plant, merged)
    return Preview(
        values=state.values,
        tiles=[state.tile(k, editable=True) for k in state.params],
        alerts=alerts(db, state),
        problems=predicted_problems(db, state).matched,
    )


def history(
    db: Session,
    principal: Principal,
    plant_id: uuid.UUID,
    page: PageParams,
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[Reading], int]:
    principal.require("readings.read")
    plant = get_plant_in_scope(db, principal, plant_id)
    query = select(Reading).where(Reading.plant_id == plant.id)
    if since:
        query = query.where(Reading.recorded_at >= since)
    if until:
        query = query.where(Reading.recorded_at <= until)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Reading.recorded_at.desc(), Reading.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    ).all()
    return list(rows), total


def _people(db: Session, readings: list[Reading]) -> dict[uuid.UUID, Person]:
    ids = {r.created_by for r in readings if r.created_by}
    if not ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(ids)))
    return {u.id: Person(id=u.id, name=u.full_name or u.username) for u in users}


def to_out(db: Session, readings: list[Reading]) -> list[ReadingOut]:
    people = _people(db, readings)
    return [
        ReadingOut(
            id=r.id,
            recorded_at=r.recorded_at,
            created_by=people.get(r.created_by) if r.created_by else None,
            source=r.source,
            input_values=r.input_values,
            calculated_values=r.calculated_values,
            formula_versions=r.formula_versions,
            settings_used=r.settings_used,
            changed_keys=r.changed_keys,
        )
        for r in readings
    ]


def summary(db: Session, reading: Reading | None) -> ReadingSummary | None:
    if reading is None:
        return None
    people = _people(db, [reading])
    return ReadingSummary(
        id=reading.id,
        recorded_at=reading.recorded_at,
        created_by=people.get(reading.created_by) if reading.created_by else None,
        changed_keys=reading.changed_keys,
    )
