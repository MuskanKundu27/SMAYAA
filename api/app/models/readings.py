import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import UuidPk


class Reading(Base):
    """One saved state of a plant's values: an event that is never changed afterwards.

    Every save (e.g. an operator changing hardness) creates a new row holding the full set of
    input values after merging the change, the calculated values at that moment, and the
    formula versions and settings used. "Current values" = the newest row; history = all rows.
    """

    __tablename__ = "readings"
    __table_args__ = (Index("ix_readings_plant_recorded", "plant_id", text("recorded_at DESC")),)

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id"))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(30), server_default="manual")
    input_values: Mapped[dict[str, Any]] = mapped_column(JSONB)
    calculated_values: Mapped[dict[str, Any]] = mapped_column(JSONB)
    formula_versions: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Plant settings used in the calculation (e.g. the clean baseline approach as `base`).
    settings_used: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    # Input keys this save changed, so the UI can show "hardness saved by X at 14:32".
    changed_keys: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default=text("'{}'"))
