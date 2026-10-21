import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.admin import AuditEntryOut
from app.schemas.common import Page, PageParams, page_params
from app.services import audit as service

router = APIRouter(prefix="/audit-log", tags=["audit log"])


@router.get("", response_model=Page[AuditEntryOut])
def list_audit_log(
    principal: CurrentPrincipal,
    db: DbSession,
    page: Annotated[PageParams, Depends(page_params)],
    company_id: Annotated[uuid.UUID | None, Query(description="Platform users only")] = None,
    entity: Annotated[str | None, Query(max_length=100, description="e.g. parameter")] = None,
) -> Page[AuditEntryOut]:
    """Who changed what, newest first."""
    items, total = service.list_entries(db, principal, page, company_id=company_id, entity=entity)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
