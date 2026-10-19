import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.common import Page, PageParams, page_params
from app.schemas.users import DeactivateResponse, UserCreate, UserOut
from app.services import users as service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserOut])
def list_users(
    principal: CurrentPrincipal, db: DbSession, page: Annotated[PageParams, Depends(page_params)]
) -> Page[UserOut]:
    items, total = service.list_users(db, principal, page)
    return Page(items=service.to_out(db, items), total=total, limit=page.limit, offset=page.offset)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, principal: CurrentPrincipal, db: DbSession) -> UserOut:
    return service.to_out(db, [service.create_user(db, principal, body)])[0]


@router.delete("/{user_id}", response_model=DeactivateResponse)
def deactivate_user(
    user_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> DeactivateResponse:
    """Deactivates the user (never deletes). Their sessions stop working immediately."""
    user, warnings = service.deactivate_user(db, principal, user_id)
    return DeactivateResponse(user=service.to_out(db, [user])[0], warnings=warnings)
