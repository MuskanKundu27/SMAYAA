"""Plant limits and plant settings."""

import uuid

from fastapi import APIRouter

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.config import PlantLimits, PlantLimitsUpdate, PlantSettings, PlantSettingsUpdate
from app.services import limits as service

router = APIRouter(prefix="/plants/{plant_id}", tags=["limits"])


@router.get("/limits", response_model=PlantLimits)
def get_limits(plant_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession) -> PlantLimits:
    """Effective limits for every active parameter; `can_edit` tells the UI whether to allow
    editing (manager, or company admin while the plant has no manager)."""
    return service.get_limits(db, principal, plant_id)


@router.put("/limits", response_model=PlantLimits)
def update_limits(
    plant_id: uuid.UUID, body: PlantLimitsUpdate, principal: CurrentPrincipal, db: DbSession
) -> PlantLimits:
    return service.update_limits(db, principal, plant_id, body)


@router.delete("/limits/{parameter_key}", response_model=PlantLimits)
def reset_limit(
    plant_id: uuid.UUID, parameter_key: str, principal: CurrentPrincipal, db: DbSession
) -> PlantLimits:
    """Go back to the company default limits for one parameter."""
    return service.reset_limit(db, principal, plant_id, parameter_key)


@router.get("/settings", response_model=PlantSettings)
def get_settings(plant_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession) -> PlantSettings:
    return service.get_settings(db, principal, plant_id)


@router.put("/settings", response_model=PlantSettings)
def update_settings(
    plant_id: uuid.UUID, body: PlantSettingsUpdate, principal: CurrentPrincipal, db: DbSession
) -> PlantSettings:
    """e.g. `{"values": {"clean_baseline_approach": 4.5}}`"""
    return service.update_settings(db, principal, plant_id, body.values)
