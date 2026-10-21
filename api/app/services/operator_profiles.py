"""Operator profiles: what each lower-ranked user at a plant may see and do.

The manager restricts; no stored row means the defaults (every module, alerts shown, may
enter readings). Applies to the users the caller may manage at that plant (the same rank rule
as the Users page), so no role names appear in code. Enforcement lives where the data is
served (services/plant_views.py, services/readings.py).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import NotFoundError, ValidationFailedError
from app.models import Module, OperatorProfile, Plant, RoleAssignment, User
from app.schemas.admin import OperatorProfileIn, OperatorProfileOut
from app.services import audit
from app.services.plants import get_plant_in_scope
from app.services.users import manageable_role_keys

PERMISSION = "operator_profiles.manage"
PROFILE_FIELDS = ["visible_modules", "can_edit_readings", "show_alerts"]


def _profiled_users(db: Session, principal: Principal, plant: Plant) -> dict[uuid.UUID, User]:
    """Active users at this plant whose role the caller may manage."""
    roles = manageable_role_keys(principal)
    users = db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            User.id.in_(
                select(RoleAssignment.user_id).where(
                    RoleAssignment.plant_id == plant.id, RoleAssignment.role_key.in_(roles)
                )
            ),
        )
        .order_by(User.username)
    )
    return {u.id: u for u in users}


def _roles_of(
    db: Session, user_ids: list[uuid.UUID], plant_id: uuid.UUID
) -> dict[uuid.UUID, list[str]]:
    result: dict[uuid.UUID, list[str]] = {u: [] for u in user_ids}
    for a in db.scalars(
        select(RoleAssignment).where(
            RoleAssignment.user_id.in_(user_ids), RoleAssignment.plant_id == plant_id
        )
    ):
        result[a.user_id].append(a.role_key)
    return result


def _out(user: User, roles: list[str], profile: OperatorProfile | None) -> OperatorProfileOut:
    return OperatorProfileOut(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        roles=sorted(roles),
        is_default=profile is None,
        visible_modules=profile.visible_modules if profile else None,
        can_edit_readings=profile.can_edit_readings if profile else True,
        show_alerts=profile.show_alerts if profile else True,
    )


def list_profiles(
    db: Session, principal: Principal, plant_id: uuid.UUID
) -> list[OperatorProfileOut]:
    principal.require(PERMISSION)
    plant = get_plant_in_scope(db, principal, plant_id)
    users = _profiled_users(db, principal, plant)
    roles = _roles_of(db, list(users), plant.id)
    profiles = {
        p.user_id: p
        for p in db.scalars(select(OperatorProfile).where(OperatorProfile.plant_id == plant.id))
    }
    return [_out(u, roles[u.id], profiles.get(u.id)) for u in users.values()]


def _target(
    db: Session, principal: Principal, plant_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Plant, User]:
    principal.require(PERMISSION)
    plant = get_plant_in_scope(db, principal, plant_id)
    user = _profiled_users(db, principal, plant).get(user_id)
    if user is None:
        raise NotFoundError("User not found at this plant.")
    return plant, user


def set_profile(
    db: Session,
    principal: Principal,
    plant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: OperatorProfileIn,
) -> OperatorProfileOut:
    plant, user = _target(db, principal, plant_id, user_id)
    if data.visible_modules is not None:
        known = set(
            db.scalars(
                select(Module.key).where(
                    Module.company_id == plant.company_id, Module.is_active.is_(True)
                )
            )
        )
        unknown = sorted(set(data.visible_modules) - known)
        if unknown:
            raise ValidationFailedError(
                "Unknown modules.",
                [
                    {"field": "visible_modules", "message": f"No active module '{k}'."}
                    for k in unknown
                ],
            )
    profile = db.get(OperatorProfile, (user.id, plant.id))
    before = audit.snapshot(profile, PROFILE_FIELDS) if profile else None
    if profile is None:
        profile = OperatorProfile(user_id=user.id, plant_id=plant.id, company_id=plant.company_id)
        db.add(profile)
    profile.visible_modules = (
        sorted(set(data.visible_modules)) if data.visible_modules is not None else None
    )
    profile.can_edit_readings = data.can_edit_readings
    profile.show_alerts = data.show_alerts
    audit.record(
        db, principal, "operator_profile.update", "operator_profile", user.id,
        company_id=plant.company_id, before=before,
        after={**audit.snapshot(profile, PROFILE_FIELDS), "plant_id": str(plant.id)},
    )  # fmt: skip
    db.commit()
    return _out(user, _roles_of(db, [user.id], plant.id)[user.id], profile)


def reset_profile(
    db: Session, principal: Principal, plant_id: uuid.UUID, user_id: uuid.UUID
) -> OperatorProfileOut:
    """Remove all restrictions (back to the defaults)."""
    plant, user = _target(db, principal, plant_id, user_id)
    profile = db.get(OperatorProfile, (user.id, plant.id))
    if profile is not None:
        audit.record(
            db, principal, "operator_profile.reset", "operator_profile", user.id,
            company_id=plant.company_id, before=audit.snapshot(profile, PROFILE_FIELDS),
            after={"plant_id": str(plant.id)},
        )  # fmt: skip
        db.delete(profile)
        db.commit()
    return _out(user, _roles_of(db, [user.id], plant.id)[user.id], None)
