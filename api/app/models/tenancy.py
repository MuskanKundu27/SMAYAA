import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAt, UuidPk


class Company(Base):
    """A tenant: one customer organisation."""

    __tablename__ = "companies"

    id: Mapped[UuidPk]
    name: Mapped[str] = mapped_column(String(200), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[CreatedAt]


class Plant(Base):
    __tablename__ = "plants"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_plants_company_name"),)

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200), server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
