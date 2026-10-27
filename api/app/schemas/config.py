import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ApiModel

PARAMETER_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,39}$"
RULE_CODE_PATTERN = r"^[A-Z0-9][A-Z0-9_-]{1,39}$"
MODULE_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,59}$"


# --- Limits ------------------------------------------------------------------------------------


class LimitValues(BaseModel):
    warn_min: float
    good_min: float
    good_max: float
    warn_max: float

    @model_validator(mode="after")
    def check_order(self) -> "LimitValues":
        if not self.warn_min <= self.good_min <= self.good_max <= self.warn_max:
            raise ValueError("Limits must satisfy warn_min ≤ good_min ≤ good_max ≤ warn_max.")
        return self


# --- Parameters --------------------------------------------------------------------------------


class ParameterCreate(BaseModel):
    key: str = Field(pattern=PARAMETER_KEY_PATTERN, description="Lower-case, e.g. 'hard'")
    label: str = Field(min_length=1, max_length=100)
    unit: str = Field(default="", max_length=30)
    group_key: str = Field(min_length=1, max_length=40, description="e.g. chemistry")
    kind: Literal["input", "calculated"]
    formula: str | None = Field(default=None, description="Required when kind is calculated")
    precision: int = Field(default=2, ge=0, le=6)
    sort_order: int = 0
    sample_value: float | None = None
    default_limits: LimitValues | None = None


class ParameterUpdate(BaseModel):
    """Only the fields sent are changed. Send default_limits: null to remove the defaults."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    unit: str | None = Field(default=None, max_length=30)
    group_key: str | None = Field(default=None, min_length=1, max_length=40)
    # Switch between measured (typed in or from a PLC) and calculated. A measured parameter
    # keeps its formula, so switching back needs no retyping.
    kind: Literal["input", "calculated"] | None = None
    formula: str | None = None
    precision: int | None = Field(default=None, ge=0, le=6)
    sort_order: int | None = None
    sample_value: float | None = None
    default_limits: LimitValues | None = None
    is_active: bool | None = None


class ParameterOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    unit: str
    group_key: str
    kind: str
    formula: str | None
    formula_version: int
    precision: int
    sort_order: int
    is_active: bool
    sample_value: float | None
    default_limits: LimitValues | None
    updated_at: datetime | None


class FormulaTest(BaseModel):
    formula: str
    values: dict[str, float | None] | None = Field(
        default=None, description="Input values; omit to use each parameter's sample value"
    )
    base: float | None = Field(default=None, description="Clean baseline approach for 'base'")


class FormulaTestResult(BaseModel):
    ok: bool
    result: float | bool | None
    references: list[str]
    error: str | None


# --- Treatments --------------------------------------------------------------------------------


class TreatmentIn(BaseModel):
    parameter_key: str
    direction: Literal["high", "low"]
    cause: str = Field(default="", max_length=2000)
    treatment: str = Field(default="", max_length=2000)
    precautions: str = Field(default="", max_length=2000)
    needs_review: bool = True


class TreatmentOut(TreatmentIn):
    id: uuid.UUID


# --- Rules -------------------------------------------------------------------------------------


Priority = Literal["high", "medium", "low"]


class RuleCreate(BaseModel):
    code: str = Field(pattern=RULE_CODE_PATTERN, description="e.g. TH-P01")
    title: str = Field(min_length=1, max_length=200)
    condition_expr: str
    probability_expr: str
    action_text: str = Field(default="", max_length=2000)
    priority: Priority = "medium"
    benefit_text: str = Field(default="", max_length=500)
    eta_expr: str | None = Field(default=None, description="Hours until expected; optional")
    affects_modules: list[str] = Field(default_factory=list)
    sort_order: int = 0


class RuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    condition_expr: str | None = None
    probability_expr: str | None = None
    action_text: str | None = Field(default=None, max_length=2000)
    priority: Priority | None = None
    benefit_text: str | None = Field(default=None, max_length=500)
    eta_expr: str | None = None  # send "" or null to remove the estimate
    affects_modules: list[str] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class RuleOut(ApiModel):
    id: uuid.UUID
    code: str
    title: str
    kind: str
    condition_expr: str
    probability_expr: str
    action_text: str
    priority: str
    benefit_text: str
    eta_expr: str | None
    affects_modules: list[str]
    is_active: bool
    version: int
    sort_order: int


class RuleTest(BaseModel):
    condition_expr: str
    probability_expr: str | None = None
    eta_expr: str | None = None
    values: dict[str, float | None] = Field(
        default_factory=dict, description="Input values (calculated values are derived)"
    )
    base: float | None = None


class RuleTestResult(BaseModel):
    ok: bool
    matched: bool | None
    probability: float | None
    eta_hours: float | None = None
    references: list[str]
    error: str | None


# --- Modules and widgets -----------------------------------------------------------------------
# The frontend has one component per widget type (the widget registry). Adding a type means
# adding a model here and a component there.

Keys = list[Annotated[str, Field(max_length=60)]]


class _Widget(BaseModel):
    title: str = Field(default="", max_length=100)
    # Share of the screen width; narrow screens always use the full width.
    width: Literal["full", "half", "third", "quarter"] = "full"


class InputGroupWidget(_Widget):
    type: Literal["input_group"]
    group: str | None = None
    params: Keys | None = None
    # On/off inputs (1 = on, 0 = off) drawn as switches instead of number boxes.
    switches: Keys | None = None

    @model_validator(mode="after")
    def needs_group_or_params(self) -> "InputGroupWidget":
        if not self.group and not self.params:
            raise ValueError("input_group needs either 'group' or 'params'.")
        return self


class ValueTilesWidget(_Widget):
    type: Literal["value_tiles"]
    params: Keys
    # Show only the listed parameters that are currently calculated (a measured one is then
    # shown with the inputs instead).
    only_calculated: bool = False


Hours = Annotated[int, Field(ge=1, le=24 * 90)]
Key = Annotated[str, Field(max_length=60)]


class TrendChartWidget(_Widget):
    type: Literal["trend_chart"]
    params: Keys
    hours: Hours = 24
    # Time-range buttons, e.g. [6, 24, 168, 720] for 6H / 24H / 7D / 30D. `hours` is the one
    # shown first.
    ranges: list[Hours] | None = Field(default=None, max_length=6)
    # Draw all series in one chart (first series on the left axis, the others on the right).
    combine: bool = False


class PredictedProblemsWidget(_Widget):
    type: Literal["predicted_problems"]
    rules: Keys
    # "table": one row per problem with severity (rule priority), probability and ETA.
    style: Literal["list", "table"] = "list"


class RecommendedActionsWidget(_Widget):
    """The recommended action, priority and expected benefit of each matched rule."""

    type: Literal["recommended_actions"]
    rules: Keys


class KpiCardItem(BaseModel):
    param: Key
    caption: str = Field(default="", max_length=100)
    # "limits": show the good range as the target; a parameter key: show "≤ its value".
    target: Key | None = None
    # Take the status colour from another parameter (e.g. blowdown coloured by its deviation
    # from the required blowdown).
    status_from: Key | None = None
    # A parameter holding a % change, shown with an up/down arrow next to the caption.
    delta: Key | None = None
    # Which way of the % change is good (green): "up" (e.g. savings) or "down" (e.g. chemical use).
    delta_good: Literal["up", "down"] = "up"
    # Caption from the status: "Within target range" / "Outside target range".
    range_caption: bool = False


class KpiCardsWidget(_Widget):
    type: Literal["kpi_cards"]
    items: list[KpiCardItem] = Field(min_length=1, max_length=20)
    style: Literal["kpi", "benefit"] = "kpi"


QUICK_LINK_TARGET = r"^(module:[a-z][a-z0-9_]{0,59}|limits|operator-profiles)$"


class QuickLink(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    # Where the button goes: a module ("module:water_chemistry") or a page ("limits").
    target: str = Field(pattern=QUICK_LINK_TARGET)


class QuickLinksWidget(_Widget):
    type: Literal["quick_links"]
    items: list[QuickLink] = Field(min_length=1, max_length=12)


class SystemDiagramWidget(_Widget):
    """A cooling-tower picture with make-up, blowdown and side-stream values and a list of
    chemistry measurement points."""

    type: Literal["system_diagram"]
    makeup: Key | None = None
    blowdown: Key | None = None
    sidestream: Key | None = None
    chemistry: Keys = Field(default_factory=list, max_length=8)


class AlertListWidget(_Widget):
    type: Literal["alert_list"]
    modules: Keys | None = None
    params: Keys | None = None


class InputsSummaryWidget(_Widget):
    type: Literal["inputs_summary"]
    params: Keys


class TextNoteWidget(_Widget):
    type: Literal["text_note"]
    text: str = Field(max_length=2000)


Widget = Annotated[
    InputGroupWidget
    | ValueTilesWidget
    | TrendChartWidget
    | PredictedProblemsWidget
    | RecommendedActionsWidget
    | KpiCardsWidget
    | QuickLinksWidget
    | SystemDiagramWidget
    | AlertListWidget
    | InputsSummaryWidget
    | TextNoteWidget,
    Field(discriminator="type"),
]


class ModuleLayout(BaseModel):
    widgets: list[Widget] = Field(default_factory=list, max_length=50)


class ModuleCreate(BaseModel):
    key: str = Field(pattern=MODULE_KEY_PATTERN)
    title: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    layout: ModuleLayout = Field(default_factory=ModuleLayout)


class ModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    layout: ModuleLayout | None = None
    is_active: bool | None = None


class ModuleOut(BaseModel):
    id: uuid.UUID
    key: str
    title: str
    sort_order: int
    is_active: bool
    layout: dict[str, Any]
    # References to parameters/rules that don't exist or are inactive. Not an error: the
    # widget shows "insufficient data" for them.
    warnings: list[str] = Field(default_factory=list)


class TemplateApplied(BaseModel):
    template: str
    added: dict[str, int]
    updated: dict[str, int] = Field(default_factory=dict)  # only with update_existing


# --- Plant limits and settings -----------------------------------------------------------------


class PlantLimitItem(BaseModel):
    parameter_key: str
    label: str
    unit: str
    group_key: str
    limits: LimitValues | None
    source: Literal["plant", "default"] | None


class PlantLimits(BaseModel):
    plant_id: uuid.UUID
    has_manager: bool
    can_edit: bool
    items: list[PlantLimitItem]


class LimitUpdateItem(LimitValues):
    parameter_key: str


class PlantLimitsUpdate(BaseModel):
    items: list[LimitUpdateItem] = Field(min_length=1, max_length=500)


class PlantSettingValue(BaseModel):
    value: Any
    source: Literal["plant", "company_default"] | None


class PlantSettings(BaseModel):
    plant_id: uuid.UUID
    can_edit: bool
    settings: dict[str, PlantSettingValue]


class PlantSettingsUpdate(BaseModel):
    values: dict[str, Any] = Field(min_length=1)
