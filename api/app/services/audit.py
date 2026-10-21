import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.models import AuditLog


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
