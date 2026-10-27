"""Per-company configuration (parameters, treatments, rules, modules) and per-plant settings
(limits, plant settings). All of it is data: customers differ by rows, not by code."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAt, UuidPk

ALL_OR_NO_LIMITS = (
    "(default_warn_min IS NULL AND default_good_min IS NULL AND default_good_max IS NULL"
    " AND default_warn_max IS NULL) OR (default_warn_min IS NOT NULL AND default_good_min IS NOT"
    " NULL AND default_good_max IS NOT NULL AND default_warn_max IS NOT NULL)"
)


class Parameter(Base):
    """A named value: typed in (kind='input') or calculated from a formula (kind='calculated').

    The key never changes after creation, because readings store values keyed by it.
    formula_version increases on every formula change, so old readings keep the version
    they were calculated with.
    """

    __tablename__ = "parameters"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_parameters_company_key"),
        CheckConstraint("kind IN ('input', 'calculated')", name="kind_valid"),
        # A measured (input) parameter may keep a formula for switching back to calculated.
        CheckConstraint(
            "kind <> 'calculated' OR formula IS NOT NULL", name="calculated_has_formula"
        ),
        CheckConstraint(ALL_OR_NO_LIMITS, name="default_limits_complete"),
    )

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(30), server_default="")
    group_key: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))
    formula: Mapped[str | None] = mapped_column(Text)
    formula_version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    precision: Mapped[int] = mapped_column(Integer, server_default=text("2"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # Typical value: pre-fills first-run data and is used to test formulas on save.
    sample_value: Mapped[float | None] = mapped_column(Float)
    # Limits used by plants that have not set their own.
    default_warn_min: Mapped[float | None] = mapped_column(Float)
    default_good_min: Mapped[float | None] = mapped_column(Float)
    default_good_max: Mapped[float | None] = mapped_column(Float)
    default_warn_max: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Limit(Base):
    """A plant's own limits for a parameter (overrides the parameter's defaults)."""

    __tablename__ = "limits"
    __table_args__ = (
        CheckConstraint(
            "warn_min <= good_min AND good_min <= good_max AND good_max <= warn_max",
            name="ordered",
        ),
    )

    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id"), primary_key=True)
    parameter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parameters.id"), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    warn_min: Mapped[float] = mapped_column(Float)
    good_min: Mapped[float] = mapped_column(Float)
    good_max: Mapped[float] = mapped_column(Float)
    warn_max: Mapped[float] = mapped_column(Float)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class PlantSetting(Base):
    """A named setting for one plant, e.g. clean_baseline_approach."""

    __tablename__ = "plant_settings"

    plant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plants.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Treatment(Base):
    """Likely cause, treatment and precautions when a parameter is too high or too low."""

    __tablename__ = "treatments"
    __table_args__ = (
        UniqueConstraint("parameter_id", "direction", name="uq_treatments_parameter_direction"),
        CheckConstraint("direction IN ('high', 'low')", name="direction_valid"),
    )

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    parameter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parameters.id"), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    cause: Mapped[str] = mapped_column(Text, server_default="")
    treatment: Mapped[str] = mapped_column(Text, server_default="")
    precautions: Mapped[str] = mapped_column(Text, server_default="")
    # Template texts are samples that a water-treatment engineer must review before real use.
    needs_review: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Rule(Base):
    """A predicted-problem rule: when condition_expr is true, show the problem with the
    probability from probability_expr and the recommended action."""

    __tablename__ = "rules"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_rules_company_code"),
        CheckConstraint("kind IN ('predicted_problem')", name="kind_valid"),
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="priority_valid"),
    )

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), server_default="predicted_problem")
    condition_expr: Mapped[str] = mapped_column(Text)
    probability_expr: Mapped[str] = mapped_column(Text)
    action_text: Mapped[str] = mapped_column(Text, server_default="")
    priority: Mapped[str] = mapped_column(String(10), server_default="medium")
    benefit_text: Mapped[str] = mapped_column(Text, server_default="")
    # Hours until the problem is expected (e.g. time for conductivity to reach its alarm level).
    # NULL or a result of None means "no estimate".
    eta_expr: Mapped[str | None] = mapped_column(Text)
    affects_modules: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)), server_default=text("'{}'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Module(Base):
    """A dashboard screen defined as an ordered list of widgets (layout JSON)."""

    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_modules_company_key"),)

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    layout: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("""'{"widgets": []}'::jsonb""")
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
