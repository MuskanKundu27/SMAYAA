import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.models import AuditLog, Company, User
from app.schemas.admin import AuditEntryOut
from app.schemas.common import PageParams


def snapshot(obj: object, fields: list[str]) -> dict[str, Any]:
    """JSON-safe copy of selected attributes, for the before/after columns."""
    result: dict[str, Any] = {}
    for field in fields:
        value = getattr(obj, field)
        if isinstance(value, uuid.UUID | datetime):
            value = value.isoformat() if isinstance(value, datetime) else str(value)
        result[field] = value
    return result


def record(
    db: Session,
    actor: Principal,
    action: str,
    entity: str,
    entity_id: uuid.UUID | str | None,
    *,
    company_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Add an audit entry to the current transaction (committed with the change itself)."""
    record_for(
        db, actor.user_id, action, entity, entity_id,
        company_id=company_id, before=before, after=after,
    )  # fmt: skip


def record_for(
    db: Session,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | str | None,
    *,
    company_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Same as record(), for code that runs without a logged-in user (e.g. the seed script)."""
    db.add(
        AuditLog(
            company_id=company_id,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
        )
    )


def list_entries(
    db: Session,
    principal: Principal,
    page: PageParams,
    *,
    company_id: uuid.UUID | None = None,
    entity: str | None = None,
) -> tuple[list[AuditEntryOut], int]:
    """Newest first. Platform users see every company (optionally filtered); everyone else
    only their own company (row-level security enforces the same)."""
    principal.require("audit.read")
    query = (
        select(AuditLog, Company.name, User.username, User.full_name)
        .outerjoin(Company, Company.id == AuditLog.company_id)
        .outerjoin(User, User.id == AuditLog.actor_id)
    )
    if not principal.is_platform:
        query = query.where(AuditLog.company_id == principal.company_id)
    elif company_id is not None:
        query = query.where(AuditLog.company_id == company_id)
    if entity:
        query = query.where(AuditLog.entity == entity)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    ).all()
    entries = []
    for entry, company_name, username, full_name in rows:
        if entry.actor_id is None:
            actor = "System"
        elif username is None:
            # The actor exists but is outside this viewer's company (a platform admin).
            actor = "SMAYAA platform"
        else:
            actor = full_name or username
        entries.append(
            AuditEntryOut(
                id=entry.id,
                created_at=entry.created_at,
                company_id=entry.company_id,
                company_name=company_name,
                actor_id=entry.actor_id,
                actor_name=actor,
                action=entry.action,
                entity=entry.entity,
                entity_id=entry.entity_id,
                before=entry.before,
                after=entry.after,
            )
        )
    return entries, total
