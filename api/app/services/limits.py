"""Plant limits and plant settings.

Who may edit: a user with `limits.write` (manager) or, only while the
plant has no active manager, a user with `limits.write_without_manager` (company admin).
"No manager" is checked at request time, never stored as a flag. Plant settings such as the
clean baseline approach follow the same rule with `plant_settings.write`.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import PermissionDeniedError, ValidationFailedError
from app.engine.status import Limits
from app.models import Company, Limit, Plant, PlantSetting
from app.schemas.config import (
    LimitValues,
    PlantLimitItem,
    PlantLimits,
    PlantLimitsUpdate,
    PlantSettings,
    PlantSettingValue,
)
from app.services import audit
from app.services.config_common import (
    PLANT_SETTING_DEFAULTS_KEY,
    active_parameters,
    default_limits,
    plant_setting_default,
)
from app.services.plants import get_plant_in_scope, plant_has_active_manager

FALLBACK_PERMISSION = "limits.write_without_manager"


def _can_edit(db: Session, principal: Principal, plant: Plant, permission: str) -> bool:
    if principal.has(permission):
        return True
    return principal.has(FALLBACK_PERMISSION) and not plant_has_active_manager(db, plant.id)


def _limits_out(limits: Limits | None) -> LimitValues | None:
    return LimitValues(**limits.__dict__) if limits else None


def plant_limits(db: Session, plant_id: uuid.UUID) -> dict[str, tuple[Limits | None, str | None]]:
    """Effective limits per active parameter key: (limits, 'plant' | 'default' | None).
    Used here and, from step 3, for statuses and alerts."""
    plant = db.get(Plant, plant_id)
    if plant is None:
        return {}
    params = active_parameters(db, plant.company_id)
    own = {
        row.parameter_id: row for row in db.scalars(select(Limit).where(Limit.plant_id == plant_id))
    }
    result: dict[str, tuple[Limits | None, str | None]] = {}
    for key, p in params.items():
        if p.id in own:
            row = own[p.id]
            result[key] = (Limits(row.warn_min, row.good_min, row.good_max, row.warn_max), "plant")
        else:
            defaults = default_limits(p)
            result[key] = (defaults, "default" if defaults else None)
    return result


def get_limits(db: Session, principal: Principal, plant_id: uuid.UUID) -> PlantLimits:
    principal.require("limits.read")
    plant = get_plant_in_scope(db, principal, plant_id)
    params = active_parameters(db, plant.company_id)
    effective = plant_limits(db, plant.id)
    items = [
        PlantLimitItem(
            parameter_key=key,
            label=p.label,
            unit=p.unit,
            group_key=p.group_key,
            limits=_limits_out(effective[key][0]),
            source=effective[key][1],
        )
        for key, p in params.items()
    ]
    return PlantLimits(
        plant_id=plant.id,
        has_manager=plant_has_active_manager(db, plant.id),
        can_edit=_can_edit(db, principal, plant, "limits.write"),
        items=items,
    )


def _require_edit(db: Session, principal: Principal, plant: Plant, permission: str) -> None:
    if not _can_edit(db, principal, plant, permission):
        if principal.has(FALLBACK_PERMISSION):
            raise PermissionDeniedError(
                "This plant has a manager. Only the manager can change its limits."
            )
        raise PermissionDeniedError("You do not have permission to change limits.")


def update_limits(
    db: Session, principal: Principal, plant_id: uuid.UUID, data: PlantLimitsUpdate
) -> PlantLimits:
    plant = get_plant_in_scope(db, principal, plant_id)
    _require_edit(db, principal, plant, "limits.write")
    params = active_parameters(db, plant.company_id)
    unknown = sorted({i.parameter_key for i in data.items} - set(params))
    if unknown:
        raise ValidationFailedError(
            f"Unknown or inactive parameter(s): {', '.join(unknown)}.",
            [{"field": "parameter_key", "message": k} for k in unknown],
        )

    effective = plant_limits(db, plant.id)
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    now = datetime.now(UTC)
    for item in data.items:
        p = params[item.parameter_key]
        old = effective[p.key][0]
        before[p.key] = old.__dict__ if old else None
        values = item.model_dump(exclude={"parameter_key"})
        after[p.key] = values
        row = db.get(Limit, (plant.id, p.id))
        if row is None:
            row = Limit(plant_id=plant.id, parameter_id=p.id, company_id=plant.company_id)
            db.add(row)
        for field, value in values.items():
            setattr(row, field, value)
        row.updated_by = principal.user_id
        row.updated_at = now
    audit.record(
        db, principal, "limits.update", "plant", plant.id,
        company_id=plant.company_id, before=before, after=after,
    )  # fmt: skip
    db.commit()
    return get_limits(db, principal, plant.id)


def reset_limit(
    db: Session, principal: Principal, plant_id: uuid.UUID, parameter_key: str
) -> PlantLimits:
    """Remove the plant's own limits for one parameter, so the default applies again."""
    plant = get_plant_in_scope(db, principal, plant_id)
    _require_edit(db, principal, plant, "limits.write")
    p = active_parameters(db, plant.company_id).get(parameter_key)
    row = db.get(Limit, (plant.id, p.id)) if p else None
    if row is not None:
        before = {k: getattr(row, k) for k in ("warn_min", "good_min", "good_max", "warn_max")}
        db.delete(row)
        audit.record(
            db, principal, "limits.reset", "plant", plant.id, company_id=plant.company_id,
            before={parameter_key: before}, after={parameter_key: "default"},
        )  # fmt: skip
        db.commit()
    return get_limits(db, principal, plant.id)


# --- Plant settings ----------------------------------------------------------------------------

# Which plant settings exist is configuration: the keys of the company's
# settings["plant_setting_defaults"] (copied from the template). All are numbers for now
# (design values, thresholds, the clean baseline approach) and formulas read them with
# setting('name').


def _setting_keys(company: Company | None) -> list[str]:
    defaults = (company.settings or {}).get(PLANT_SETTING_DEFAULTS_KEY, {}) if company else {}
    return list(defaults)


def plant_settings_values(db: Session, plant: Plant) -> dict[str, float]:
    """Every numeric plant setting: the plant's own values over the company defaults."""
    company = db.get(Company, plant.company_id)
    values: dict[str, Any] = (
        {key: plant_setting_default(company, key) for key in _setting_keys(company)}
        if company
        else {}
    )
    for row in db.scalars(select(PlantSetting).where(PlantSetting.plant_id == plant.id)):
        values[row.key] = row.value
    return {
        k: float(v) for k, v in values.items()
        if isinstance(v, int | float) and not isinstance(v, bool)
    }  # fmt: skip


def plant_setting(db: Session, plant: Plant, key: str) -> Any:
    """The plant's own value, else the company default (from the template), else None."""
    row = db.get(PlantSetting, (plant.id, key))
    if row is not None:
        return row.value
    company = db.get(Company, plant.company_id)
    return plant_setting_default(company, key) if company else None


def get_settings(db: Session, principal: Principal, plant_id: uuid.UUID) -> PlantSettings:
    principal.require("limits.read")
    plant = get_plant_in_scope(db, principal, plant_id)
    company = db.get(Company, plant.company_id)
    result: dict[str, PlantSettingValue] = {}
    for key in _setting_keys(company):
        row = db.get(PlantSetting, (plant.id, key))
        if row is not None:
            result[key] = PlantSettingValue(value=row.value, source="plant")
        else:
            default = plant_setting_default(company, key) if company else None
            result[key] = PlantSettingValue(
                value=default, source="company_default" if default is not None else None
            )
    return PlantSettings(
        plant_id=plant.id,
        can_edit=_can_edit(db, principal, plant, "plant_settings.write"),
        settings=result,
    )


def update_settings(
    db: Session, principal: Principal, plant_id: uuid.UUID, values: dict[str, Any]
) -> PlantSettings:
    plant = get_plant_in_scope(db, principal, plant_id)
    _require_edit(db, principal, plant, "plant_settings.write")
    known_keys = set(_setting_keys(db.get(Company, plant.company_id)))
    problems = []
    for key, value in values.items():
        if key not in known_keys:
            problems.append({"field": key, "message": "Unknown setting."})
        elif isinstance(value, bool) or not isinstance(value, int | float):
            problems.append({"field": key, "message": "Must be a number."})
    if problems:
        raise ValidationFailedError("Invalid plant settings.", problems)

    before = {k: plant_setting(db, plant, k) for k in values}
    now = datetime.now(UTC)
    for key, value in values.items():
        row = db.get(PlantSetting, (plant.id, key))
        if row is None:
            row = PlantSetting(plant_id=plant.id, key=key, company_id=plant.company_id)
            db.add(row)
        row.value = float(value)
        row.updated_by = principal.user_id
        row.updated_at = now
    audit.record(
        db, principal, "plant_settings.update", "plant", plant.id,
        company_id=plant.company_id, before=before, after=values,
    )  # fmt: skip
    db.commit()
    return get_settings(db, principal, plant.id)
