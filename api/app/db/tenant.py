"""Per-request tenant context for Postgres row-level security (RLS).

Every transaction on a Session starts by copying the session's TenantContext into Postgres
settings (app.user_id, app.company_id, app.plant_ids, app.platform) with set_config(..., true),
i.e. local to that transaction. The RLS policies (migration 0002) read those settings.

Why on every transaction: a service may commit and keep working; the next transaction must
carry the same context. A session with no context gets DENY_ALL, so forgetting to set it
fails closed (no rows) instead of leaking rows.
"""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, event, text
from sqlalchemy.orm import Session, SessionTransaction

ALL_PLANTS: Literal["*"] = "*"


@dataclass(frozen=True)
class TenantContext:
    user_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    # "*" = every plant of company_id; otherwise the explicit plants the user is assigned to.
    plant_ids: Literal["*"] | tuple[uuid.UUID, ...] = ()
    platform: bool = False

    def as_settings(self) -> dict[str, str]:
        plants = (
            ALL_PLANTS if self.plant_ids == ALL_PLANTS else ",".join(str(p) for p in self.plant_ids)
        )
        return {
            "user_id": str(self.user_id) if self.user_id else "",
            "company_id": str(self.company_id) if self.company_id else "",
            "plant_ids": plants,
            "platform": "on" if self.platform else "off",
        }


DENY_ALL = TenantContext()

_SET_SQL = text(
    "SELECT set_config('app.user_id', :user_id, true),"
    " set_config('app.company_id', :company_id, true),"
    " set_config('app.plant_ids', :plant_ids, true),"
    " set_config('app.platform', :platform, true)"
)


def _write_settings(connection: Connection, context: TenantContext) -> None:
    connection.execute(_SET_SQL, context.as_settings())


@event.listens_for(Session, "after_begin")
def _apply_on_begin(
    session: Session, _transaction: SessionTransaction, connection: Connection
) -> None:
    _write_settings(connection, session.info.get("tenant", DENY_ALL))


def set_tenant_context(session: Session, context: TenantContext) -> None:
    """Use this context for the rest of the session, including the current transaction."""
    session.info["tenant"] = context
    if session.in_transaction():
        _write_settings(session.connection(), context)
