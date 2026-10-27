"""Plant readings, alerts and module screens."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.common import Page, PageParams, page_params
from app.schemas.readings import (
    ModuleSummary,
    ModuleView,
    PlantAlerts,
    Preview,
    ReadingInput,
    ReadingOut,
    SaveResult,
    TrendSeries,
)
from app.services import plant_views, readings
from app.services.plants import get_plant_in_scope

router = APIRouter(prefix="/plants/{plant_id}", tags=["readings, alerts and modules"])


@router.post("/readings", response_model=SaveResult)
def save_reading(
    plant_id: uuid.UUID,
    body: ReadingInput,
    response: Response,
    principal: CurrentPrincipal,
    db: DbSession,
) -> SaveResult:
    """Send only the changed values, e.g. `{"values": {"hard": 650}}`. A new reading is stored
    (201) with everything recalculated; if nothing changed, the latest reading is returned (200)."""
    reading, created = readings.save_reading(db, principal, plant_id, body.values)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return SaveResult(reading=readings.to_out(db, [reading])[0], created=created)


@router.post("/readings/preview", response_model=Preview)
def preview_reading(
    plant_id: uuid.UUID, body: ReadingInput, principal: CurrentPrincipal, db: DbSession
) -> Preview:
    """Live preview while typing: values, statuses, alerts and problems. Nothing is stored."""
    return readings.preview(db, principal, plant_id, body.values)


@router.get("/readings/latest", response_model=ReadingOut | None)
def latest_reading(
    plant_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> ReadingOut | None:
    """The newest reading (or null). Screens poll this and reload when the id changes."""
    principal.require("readings.read")
    plant = get_plant_in_scope(db, principal, plant_id)
    latest = readings.latest_reading(db, plant.id)
    return readings.to_out(db, [latest])[0] if latest else None


@router.get("/readings", response_model=Page[ReadingOut])
def reading_history(
    plant_id: uuid.UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    page: Annotated[PageParams, Depends(page_params)],
    since: Annotated[datetime | None, Query(alias="from")] = None,
    until: Annotated[datetime | None, Query(alias="to")] = None,
) -> Page[ReadingOut]:
    """History, newest first. Values are exactly as calculated when each reading was saved."""
    items, total = readings.history(db, principal, plant_id, page, since, until)
    return Page(items=readings.to_out(db, items), total=total, limit=page.limit, offset=page.offset)


@router.get("/alerts", response_model=PlantAlerts)
def plant_alerts(plant_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession) -> PlantAlerts:
    """Alerts from the latest reading and current limits (for the alert bar on every page)."""
    return plant_views.plant_alerts(db, principal, plant_id)


@router.get("/modules", response_model=list[ModuleSummary])
def list_modules(
    plant_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ModuleSummary]:
    """Modules this user may open at this plant (drives the module menu)."""
    return plant_views.list_modules(db, principal, plant_id)


@router.get("/modules/{key}", response_model=ModuleView)
def module_view(
    plant_id: uuid.UUID, key: str, principal: CurrentPrincipal, db: DbSession
) -> ModuleView:
    """A module's widgets with the data each needs to be drawn."""
    return plant_views.module_view(db, principal, plant_id, key)


@router.get("/modules/{key}/trend", response_model=list[TrendSeries])
def module_trend(
    plant_id: uuid.UUID,
    key: str,
    principal: CurrentPrincipal,
    db: DbSession,
    widget: Annotated[int, Query(ge=0, description="Position of the chart in the layout")],
    hours: Annotated[int, Query(ge=1, le=24 * 90)],
) -> list[TrendSeries]:
    """One trend chart's series for another of its time ranges (e.g. 6H / 24H / 7D / 30D)."""
    return plant_views.module_trend(db, principal, plant_id, key, widget, hours)
