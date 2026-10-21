"""Operator profiles (manager): which modules and actions each operator gets at a plant."""

import uuid

from fastapi import APIRouter

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.admin import OperatorProfileIn, OperatorProfileOut
from app.services import operator_profiles as service

router = APIRouter(prefix="/plants/{plant_id}/operator-profiles", tags=["operator profiles"])


@router.get("", response_model=list[OperatorProfileOut])
def list_profiles(
    plant_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> list[OperatorProfileOut]:
    return service.list_profiles(db, principal, plant_id)


@router.put("/{user_id}", response_model=OperatorProfileOut)
def set_profile(
    plant_id: uuid.UUID,
    user_id: uuid.UUID,
    body: OperatorProfileIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> OperatorProfileOut:
    return service.set_profile(db, principal, plant_id, user_id, body)


@router.delete("/{user_id}", response_model=OperatorProfileOut)
def reset_profile(
    plant_id: uuid.UUID, user_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> OperatorProfileOut:
    """Remove the restrictions; the operator gets the defaults (everything) again."""
    return service.reset_profile(db, principal, plant_id, user_id)
