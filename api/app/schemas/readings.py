import math
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.config import LimitValues


class ReadingInput(BaseModel):
    """Only the fields that changed. `null` clears a value."""

    values: dict[str, float | None] = Field(min_length=1, max_length=200)

    @field_validator("values")
    @classmethod
    def finite_numbers(cls, values: dict[str, float | None]) -> dict[str, float | None]:
        for key, value in values.items():
            if value is not None and not math.isfinite(value):
                raise ValueError(f"'{key}' must be a finite number.")
        return values


class Person(BaseModel):
    id: uuid.UUID
    name: str


class ReadingOut(BaseModel):
    id: uuid.UUID
    recorded_at: datetime
    created_by: Person | None
    source: str
    input_values: dict[str, float | None]
    calculated_values: dict[str, float | None]
    formula_versions: dict[str, int]
    settings_used: dict[str, Any]
    changed_keys: list[str]


class SaveResult(BaseModel):
    reading: ReadingOut
    created: bool = Field(description="False when nothing changed (no new reading stored)")


Severity = Literal["medium", "high"]


class Alert(BaseModel):
    parameter_key: str
    label: str
    unit: str
    value: float
    level: Literal["warn", "bad"]
    severity: Severity
    direction: Literal["high", "low"]
    limits: LimitValues
    modules: list[str] = Field(description="Module keys this parameter affects")
    cause: str
    treatment: str
    precautions: str
    needs_review: bool = Field(description="True for sample text not yet reviewed by an engineer")


class PredictedProblem(BaseModel):
    code: str
    title: str
    probability: float | None
    action: str
    modules: list[str]


class Tile(BaseModel):
    """One parameter on a screen."""

    key: str
    label: str
    unit: str = ""
    precision: int = 2
    kind: Literal["input", "calculated"] | None = None
    value: float | None = None
    status: Literal["good", "warn", "bad", "na"] = "na"
    direction: Literal["high", "low"] | None = None
    limits: LimitValues | None = None
    editable: bool = False
    insufficient_data: bool = Field(
        default=False, description="The parameter is missing or inactive in this company"
    )


class TrendPoint(BaseModel):
    t: datetime
    v: float | None


class TrendSeries(BaseModel):
    key: str
    label: str
    unit: str
    limits: LimitValues | None
    points: list[TrendPoint]


class WidgetView(BaseModel):
    """A widget from the module layout plus the data needed to draw it."""

    type: str
    title: str = ""
    tiles: list[Tile] | None = None
    switches: list[str] | None = Field(
        default=None, description="Tile keys shown as on/off switches (input_group)"
    )
    problems: list[PredictedProblem] | None = None
    insufficient_rules: list[str] | None = Field(
        default=None, description="Rule codes that cannot be evaluated (missing data/config)"
    )
    alerts: list[Alert] | None = None
    series: list[TrendSeries] | None = None
    text: str | None = None


class ReadingSummary(BaseModel):
    id: uuid.UUID
    recorded_at: datetime
    created_by: Person | None
    changed_keys: list[str]


class ModuleSummary(BaseModel):
    key: str
    title: str
    sort_order: int


class ModuleView(BaseModel):
    key: str
    title: str
    reading: ReadingSummary | None
    can_edit_readings: bool
    widgets: list[WidgetView]


class PlantAlerts(BaseModel):
    """For the notification bell: what is out of range and which problems are predicted."""

    reading: ReadingSummary | None
    alerts: list[Alert]
    problems: list[PredictedProblem] = Field(default_factory=list)


class Preview(BaseModel):
    """What the screen would show if these values were saved. Nothing is stored."""

    values: dict[str, float | None]
    tiles: list[Tile]
    alerts: list[Alert]
    problems: list[PredictedProblem]
