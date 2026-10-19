import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models import Plant, RoleAssignment, RolePermission, User
from app.schemas.common import PageParams
from app.schemas.tenancy import PlantCreate, PlantUpdate
from app.services import audit

PLANT_FIELDS = ["name", "location", "is_active"]

# A plant "has a manager" when an active user assigned to it holds this permission.
# Checked from data, so a custom role with limit-editing rights counts too.
LIMIT_EDITOR_PERMISSION = "limits.write"


def _visible_plants(principal: Principal) -> Select[tuple[Plant]]:
    query = select(Plant).where(Plant.company_id == principal.company_id)
    if principal.plant_ids is not None:
        query = query.where(Plant.id.in_(principal.plant_ids))
    return query


def list_plants(db: Session, principal: Principal, page: PageParams) -> tuple[list[Plant], int]:
    principal.require("plants.read")
    query = _visible_plants(principal)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    plants = db.scalars(query.order_by(Plant.name).limit(page.limit).offset(page.offset)).all()
    return list(plants), total


def get_plant_in_scope(db: Session, principal: Principal, plant_id: uuid.UUID) -> Plant:
    """The plant, if this principal may see it; otherwise 404 (we do not reveal it exists)."""
    plant = db.get(Plant, plant_id)
    if (
        plant is None
        or plant.company_id != principal.company_id
        or not principal.can_see_plant(plant.id)
    ):
        raise NotFoundError("Plant not found.")
    return plant


def _ensure_name_free(
    db: Session, company_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> None:
    query = select(Plant.id).where(Plant.company_id == company_id, Plant.name == name)
    if exclude:
        query = query.where(Plant.id != exclude)
    if db.scalar(query) is not None:
        raise ConflictError(f"A plant named '{name}' already exists.")


def create_plant(db: Session, principal: Principal, data: PlantCreate) -> Plant:
    principal.require("plants.manage")
    if principal.company_id is None:  # a platform user granted plants.manage by mistake
        raise PermissionDeniedError("Plants belong to a company; log in as a company user.")
    _ensure_name_free(db, principal.company_id, data.name)
    plant = Plant(company_id=principal.company_id, name=data.name, location=data.location)
    db.add(plant)
    db.flush()
    audit.record(
        db, principal, "plant.create", "plant", plant.id,
        company_id=plant.company_id, after=audit.snapshot(plant, PLANT_FIELDS),
    )  # fmt: skip
    db.commit()
    return plant


def update_plant(
    db: Session, principal: Principal, plant_id: uuid.UUID, data: PlantUpdate
) -> Plant:
    principal.require("plants.manage")
    plant = get_plant_in_scope(db, principal, plant_id)
    before = audit.snapshot(plant, PLANT_FIELDS)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != plant.name:
        _ensure_name_free(db, plant.company_id, changes["name"], exclude=plant.id)
    for field, value in changes.items():
        setattr(plant, field, value)
    plant.updated_at = datetime.now(UTC)
    audit.record(
        db, principal, "plant.update", "plant", plant.id,
        company_id=plant.company_id, before=before, after=audit.snapshot(plant, PLANT_FIELDS),
    )  # fmt: skip
    db.commit()
    return plant


def plant_has_active_manager(db: Session, plant_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(
                exists()
                .where(RoleAssignment.plant_id == plant_id)
                .where(RoleAssignment.user_id == User.id, User.is_active.is_(True))
                .where(
                    RolePermission.role_key == RoleAssignment.role_key,
                    RolePermission.permission == LIMIT_EDITOR_PERMISSION,
                )
            )
        )
    )
