"""Operator profiles and the audit log."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OperatorProfileIn(BaseModel):
    """visible_modules: null = every module (also modules added later)."""

    visible_modules: list[str] | None = Field(default=None, max_length=100)
    can_edit_readings: bool = True
    show_alerts: bool = True


class OperatorProfileOut(OperatorProfileIn):
    user_id: uuid.UUID
    username: str
    full_name: str
    roles: list[str]
    # True when no restrictions are stored, i.e. the defaults apply (everything allowed).
    is_default: bool


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    company_id: uuid.UUID | None
    company_name: str | None
    actor_id: uuid.UUID | None
    actor_name: str | None
    action: str
    entity: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
