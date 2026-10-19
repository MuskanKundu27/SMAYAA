import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.common import Page, PageParams, page_params
from app.schemas.tenancy import PlantCreate, PlantOut, PlantUpdate
from app.services import plants as service

router = APIRouter(prefix="/plants", tags=["plants"])


@router.get("", response_model=Page[PlantOut])
def list_plants(
    principal: CurrentPrincipal, db: DbSession, page: Annotated[PageParams, Depends(page_params)]
) -> Page[PlantOut]:
    items, total = service.list_plants(db, principal, page)
    return Page(
        items=[PlantOut.model_validate(p) for p in items],
        total=total, limit=page.limit, offset=page.offset,
    )  # fmt: skip


@router.post("", response_model=PlantOut, status_code=status.HTTP_201_CREATED)
def create_plant(body: PlantCreate, principal: CurrentPrincipal, db: DbSession) -> PlantOut:
    return PlantOut.model_validate(service.create_plant(db, principal, body))


@router.patch("/{plant_id}", response_model=PlantOut)
def update_plant(
    plant_id: uuid.UUID, body: PlantUpdate, principal: CurrentPrincipal, db: DbSession
) -> PlantOut:
    return PlantOut.model_validate(service.update_plant(db, principal, plant_id, body))
