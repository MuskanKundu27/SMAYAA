"""Creating, listing and deactivating users.

Rules (CLAUDE brief §5):
- You may only manage users whose role you hold a `users.manage:<role>` permission for, and
  whose role rank is lower than yours (the "rank rule").
- Scope: company-wide users manage their own company; plant users only their own plants;
  platform users manage company admins of any company.
- Delete = deactivate. A deactivated user is locked out on their next request.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.security import hash_password, password_problems
from app.models import Company, Plant, Role, RoleAssignment, User
from app.schemas.common import PageParams
from app.schemas.users import UserCreate, UserOut
from app.services import audit
from app.services import auth as auth_service
from app.services.plants import plant_has_active_manager

USER_FIELDS = ["username", "full_name", "is_active", "company_id"]
MANAGE_PREFIX = "users.manage:"


def _manageable_role_keys(principal: Principal) -> list[str]:
    return [
        p.removeprefix(MANAGE_PREFIX) for p in principal.permissions if p.startswith(MANAGE_PREFIX)
    ]


def _check_can_manage_role(principal: Principal, role: Role) -> None:
    principal.require(f"{MANAGE_PREFIX}{role.key}")
    if role.rank >= principal.rank:
        raise PermissionDeniedError("You can only manage users with a lower role than yours.")


def _username_taken(db: Session, username: str) -> bool:
    # auth_find_user sees every company, so usernames stay unique platform-wide.
    row = db.execute(
        text("SELECT 1 FROM auth_find_user(:username, NULL)"), {"username": username}
    ).first()
    return row is not None


def create_user_record(
    db: Session,
    principal: Principal,
    *,
    username: str,
    full_name: str,
    password: str,
    role: Role,
    company_id: uuid.UUID | None,
    plant_id: uuid.UUID | None,
) -> User:
    """Insert a user and their role assignment. Callers have already checked permissions."""
    username = username.lower()
    problems = password_problems(password, username)
    if problems:
        raise ValidationFailedError(
            "Password is too weak.", [{"field": "password", "message": p} for p in problems]
        )
    if _username_taken(db, username):
        raise ConflictError(f"The username '{username}' is already taken.")

    user = User(
        company_id=company_id,
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        created_by=principal.user_id,
    )
    db.add(user)
    db.flush()
    db.add(
        RoleAssignment(user_id=user.id, role_key=role.key, company_id=company_id, plant_id=plant_id)
    )
    audit.record(
        db, principal, "user.create", "user", user.id, company_id=company_id,
        after={**audit.snapshot(user, USER_FIELDS), "role": role.key,
               "plant_id": str(plant_id) if plant_id else None},
    )  # fmt: skip
    return user


def create_user(db: Session, principal: Principal, data: UserCreate) -> User:
    role = db.get(Role, data.role)
    if role is None:
        raise ValidationFailedError(
            "Unknown role.", [{"field": "role", "message": f"No role '{data.role}'."}]
        )
    _check_can_manage_role(principal, role)

    plant_id: uuid.UUID | None = None
    if role.scope == "company":
        if data.plant_id is not None:
            raise ValidationFailedError(f"A {role.name} is not assigned to a single plant.")
        if principal.is_platform:
            company_id = data.company_id
        elif data.company_id in (None, principal.company_id):
            company_id = principal.company_id
        else:
            raise NotFoundError("Company not found.")
        if company_id is None:
            raise ValidationFailedError(
                "company_id is required.", [{"field": "company_id", "message": "Required."}]
            )
        if db.get(Company, company_id) is None:
            raise NotFoundError("Company not found.")
    elif role.scope == "plant":
        if data.plant_id is None:
            raise ValidationFailedError(
                "plant_id is required.", [{"field": "plant_id", "message": "Required."}]
            )
        plant = db.get(Plant, data.plant_id)
        if (
            plant is None
            or plant.company_id != principal.company_id
            or not principal.can_see_plant(plant.id)
        ):
            raise NotFoundError("Plant not found.")
        if not plant.is_active:
            raise ValidationFailedError("This plant is deactivated.")
        company_id, plant_id = plant.company_id, plant.id
    else:
        raise PermissionDeniedError("Platform users cannot be created through the API.")

    user = create_user_record(
        db, principal, username=data.username, full_name=data.full_name,
        password=data.password, role=role, company_id=company_id, plant_id=plant_id,
    )  # fmt: skip
    db.commit()
    return user


def list_users(db: Session, principal: Principal, page: PageParams) -> tuple[list[User], int]:
    principal.require("users.read")
    query = select(User)
    if principal.is_platform:
        query = query.where(
            User.id.in_(
                select(RoleAssignment.user_id).where(
                    RoleAssignment.role_key.in_(_manageable_role_keys(principal))
                )
            )
        )
    elif principal.plant_ids is None:
        query = query.where(User.company_id == principal.company_id)
    else:
        query = query.where(
            User.id.in_(
                select(RoleAssignment.user_id).where(
                    RoleAssignment.plant_id.in_(principal.plant_ids)
                )
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    users = db.scalars(query.order_by(User.username).limit(page.limit).offset(page.offset)).all()
    return list(users), total


def _target_in_scope(principal: Principal, target: User, assignments: list[RoleAssignment]) -> bool:
    if principal.is_platform:
        return True
    if target.company_id != principal.company_id:
        return False
    if principal.plant_ids is None:
        return True
    plant_ids = {a.plant_id for a in assignments}
    return bool(plant_ids) and all(p in principal.plant_ids for p in plant_ids)


def deactivate_user(
    db: Session, principal: Principal, user_id: uuid.UUID
) -> tuple[User, list[str]]:
    target = db.get(User, user_id)
    rows = (
        db.execute(
            select(RoleAssignment, Role)
            .join(Role, Role.key == RoleAssignment.role_key)
            .where(RoleAssignment.user_id == user_id)
        ).all()
        if target
        else []
    )
    assignments = [a for a, _ in rows]
    if target is None or not _target_in_scope(principal, target, assignments):
        raise NotFoundError("User not found.")
    if target.id == principal.user_id:
        raise ConflictError("You cannot deactivate your own account.")
    for _, role in rows:
        _check_can_manage_role(principal, role)
    if not target.is_active:
        return target, []

    before = audit.snapshot(target, USER_FIELDS)
    target.is_active = False
    target.deactivated_at = datetime.now(UTC)
    target.deactivated_by = principal.user_id
    auth_service.revoke_all_for_user(db, target.id)
    audit.record(
        db, principal, "user.deactivate", "user", target.id, company_id=target.company_id,
        before=before, after=audit.snapshot(target, USER_FIELDS),
    )  # fmt: skip
    db.flush()

    warnings = []
    for plant_id in {a.plant_id for a in assignments if a.plant_id is not None}:
        if not plant_has_active_manager(db, plant_id):
            plant = db.get(Plant, plant_id)
            name = plant.name if plant else str(plant_id)
            warnings.append(
                f"Plant '{name}' has no manager now. The company admin can edit its limits "
                "until a new manager is assigned."
            )
    db.commit()
    return target, warnings


def to_out(db: Session, users: list[User]) -> list[UserOut]:
    """Attach roles and plants to users with one query (not one per user)."""
    assignments: defaultdict[uuid.UUID, list[RoleAssignment]] = defaultdict(list)
    if users:
        for a in db.scalars(
            select(RoleAssignment).where(RoleAssignment.user_id.in_([u.id for u in users]))
        ):
            assignments[a.user_id].append(a)
    return [
        UserOut(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            is_active=u.is_active,
            company_id=u.company_id,
            roles=sorted({a.role_key for a in assignments[u.id]}),
            plant_ids=sorted({a.plant_id for a in assignments[u.id] if a.plant_id}),
            created_at=u.created_at,
            deactivated_at=u.deactivated_at,
        )
        for u in users
    ]
