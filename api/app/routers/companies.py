import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.common import Page, PageParams, page_params
from app.schemas.tenancy import CompanyCreate, CompanyCreated, CompanyOut, CompanyUpdate
from app.services import companies as service
from app.services.users import to_out

router = APIRouter(prefix="/companies", tags=["companies (super admin)"])


@router.get("", response_model=Page[CompanyOut])
def list_companies(
    principal: CurrentPrincipal, db: DbSession, page: Annotated[PageParams, Depends(page_params)]
) -> Page[CompanyOut]:
    items, total = service.list_companies(db, principal, page)
    return Page(
        items=[CompanyOut.model_validate(c) for c in items],
        total=total, limit=page.limit, offset=page.offset,
    )  # fmt: skip


@router.post("", response_model=CompanyCreated, status_code=status.HTTP_201_CREATED)
def create_company(
    body: CompanyCreate, principal: CurrentPrincipal, db: DbSession
) -> CompanyCreated:
    company, admin = service.create_company(db, principal, body)
    return CompanyCreated(company=CompanyOut.model_validate(company), admin=to_out(db, [admin])[0])


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: uuid.UUID, body: CompanyUpdate, principal: CurrentPrincipal, db: DbSession
) -> CompanyOut:
    return CompanyOut.model_validate(service.update_company(db, principal, company_id, body))
