"""The default SMAYAA template: Water Chemistry, Filter and Thermal.

This is product data, not logic. A new company receives a copy; changing a company's copy
never changes this template or any other company.

IMPORTANT: treatment/precaution texts are SAMPLE content and are flagged needs_review. They
must be reviewed by a qualified water-treatment engineer before real use. The LSI formula is
a demo formula until the real one is supplied. Rule probabilities are demo heuristics.
"""

from dataclasses import dataclass, field
from typing import Any

L = tuple[float, float, float, float]  # warn_min, good_min, good_max, warn_max


@dataclass(frozen=True)
class TemplateParameter:
    key: str
    label: str
    unit: str
    group: str
    sample: float | None = None
    limits: L | None = None
    formula: str | None = None
    precision: int = 2


@dataclass(frozen=True)
class TemplateTreatment:
    key: str
    direction: str  # high | low
    cause: str
    treatment: str
    precautions: str


@dataclass(frozen=True)
class TemplateRule:
    code: str
    title: str
    condition: str
    probability: str
    action: str
    affects: tuple[str, ...]


@dataclass(frozen=True)
class TemplateModule:
    key: str
    title: str
    widgets: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    parameters: list[TemplateParameter]
    treatments: list[TemplateTreatment]
    rules: list[TemplateRule]
    modules: list[TemplateModule]
    # Company-wide defaults for plant settings (a plant may override them).
    plant_setting_defaults: dict[str, Any]


P = TemplateParameter

PARAMETERS = [
    # Chemistry (typed in)
    P("ph", "pH", "", "chemistry", 7.9, (6.8, 7.2, 8.2, 8.8)),
    P("cond", "Conductivity", "µS/cm", "chemistry", 2400, (800, 1200, 2800, 3400), precision=0),
    P("tds", "TDS", "ppm", "chemistry", 1500, (500, 800, 1800, 2200), precision=0),
    P("hard", "Hardness", "ppm", "chemistry", 650, (100, 200, 600, 800), precision=0),
    P("alk", "Alkalinity", "ppm", "chemistry", 300, (100, 150, 350, 450), precision=0),
    P("sio2", "Silica", "ppm", "chemistry", 95, (0, 0, 120, 150), precision=0),
    P("mic", "Microbial count", "CFU/mL", "chemistry", 600, (0, 0, 1000, 5000), precision=0),
    # Thermal (typed in)
    P("ts", "Supply temperature", "°C", "thermal", 31, (20, 25, 32, 35), precision=1),
    P("tr", "Return temperature", "°C", "thermal", 39, (30, 35, 42, 45), precision=1),
    P("wbt", "Wet-bulb temperature", "°C", "thermal", 26, precision=1),
    P("flow", "Circulating flow", "m³/h", "thermal", 1000, (500, 700, 1300, 1500), precision=0),
    P("fan", "Fan power", "kW", "thermal", 70, (0, 0, 80, 95), precision=1),
    # Filter (typed in, no limits)
    P("pin", "Inlet pressure", "bar", "filter", 2.4),
    P("pout", "Outlet pressure", "bar", "filter", 1.8),
    P("tin", "Inlet turbidity", "NTU", "filter", 12, precision=1),
    P("tout", "Outlet turbidity", "NTU", "filter", 2, precision=1),
    P("bwf", "Backwash flow", "m³/h", "filter", 30, precision=1),
    P("bwt", "Backwash time", "min", "filter", 6, precision=1),
    # Calculated
    P("lsi", "LSI (demo formula)", "", "chemistry", limits=(-1, -0.5, 0.8, 1.5),
      formula="ph - 7.6 + (hard - 400) / 800 + (alk - 250) / 600"),
    P("range", "Range", "°C", "thermal", limits=(3, 5, 10, 12), formula="tr - ts", precision=1),
    P("appr", "Approach", "°C", "thermal", limits=(2, 3, 6, 8), formula="ts - wbt", precision=1),
    P("heat", "Heat load", "kW", "thermal", formula="1.163 * flow * (tr - ts)", precision=0),
    P("resid", "Approach residual", "°C", "thermal", limits=(-2, -2, 1.5, 3),
      formula="appr - base", precision=1),
    P("dp", "Filter ΔP", "bar", "filter", limits=(0, 0, 0.8, 1.2), formula="pin - pout"),
    P("rem", "Removal efficiency", "%", "filter", limits=(50, 70, 100, 100),
      formula="(tin - tout) / tin * 100", precision=1),
    P("bw", "Water per cleaning", "m³", "filter", formula="bwf * bwt / 60", precision=1),
]  # fmt: skip


T = TemplateTreatment

# SAMPLE TEXT - must be reviewed by a qualified water-treatment engineer before real use.
TREATMENTS = [
    T("ph", "high", "Over-concentration or high alkalinity in make-up water.",
      "Adjust acid dosing to bring pH back into range; check blowdown rate.",
      "Handle acid with PPE; change dosing in small steps and re-test."),
    T("ph", "low", "Acid overdosing or acidic contamination.",
      "Reduce or stop acid feed; investigate contamination source.",
      "Low pH accelerates corrosion; inspect metal surfaces if prolonged."),
    T("cond", "high", "Cycles of concentration too high; insufficient blowdown.",
      "Increase blowdown; verify conductivity controller and blowdown valve.",
      "Check make-up water supply can cover the extra blowdown."),
    T("cond", "low", "Excessive blowdown or make-up water dilution.",
      "Reduce blowdown; check for leaking blowdown valve.",
      "Low cycles waste water and treatment chemicals."),
    T("tds", "high", "High cycles of concentration or poor make-up quality.",
      "Increase blowdown; review make-up water treatment.", "Monitor scaling indicators (LSI)."),
    T("hard", "high", "Hard make-up water or high cycles of concentration.",
      "Increase blowdown; check softener/inhibitor dosing.",
      "Scaling risk on heat-exchange surfaces; watch approach temperature."),
    T("alk", "high", "Alkaline make-up water or insufficient acid feed.",
      "Adjust acid dosing; increase blowdown if needed.",
      "Raises scaling tendency together with pH."),
    T("sio2", "high", "Silica-rich make-up water and high cycles.",
      "Reduce cycles of concentration; consider silica inhibitor.",
      "Silica scale is very hard to remove; act early."),
    T("mic", "high", "Insufficient biocide, warm stagnant water or nutrient ingress.",
      "Shock-dose biocide; check oxidising biocide residual; clean basin.",
      "Legionella risk: follow site health & safety procedures."),
    T("ts", "high", "Reduced cooling capacity: fouled fill, fan problems or high wet-bulb.",
      "Check fans, airflow and fill condition; review heat load.",
      "High supply temperature can affect process equipment."),
    T("tr", "high", "High process heat load or low circulating flow.",
      "Check circulating flow and process load.", "Confirm temperature sensor calibration."),
    T("flow", "low", "Pump problem, closed valve or strainer blockage.",
      "Inspect pumps, valves and strainers.", "Low flow raises range and fouling risk."),
    T("fan", "high", "Fan blade pitch, bearing or motor problem; high airflow demand.",
      "Inspect fan mechanics and motor current.", "Lock out the fan before inspection."),
    T("lsi", "high", "Water is scale-forming (high pH, hardness or alkalinity).",
      "Lower pH/alkalinity with acid feed; increase blowdown; check scale inhibitor.",
      "Demo LSI formula: confirm with the real LSI calculation."),
    T("lsi", "low", "Water is corrosive (low pH or low hardness/alkalinity).",
      "Reduce acid feed; check corrosion inhibitor levels.", "Inspect corrosion coupons."),
    T("appr", "high", "Fouled fill, poor air/water distribution or fan issues.",
      "Inspect fill and nozzles; check fans; increase side-stream filtration.",
      "Compare with the clean baseline approach."),
    T("resid", "high", "Tower performing worse than its clean baseline: fouling or airflow loss.",
      "Inspect fill, nozzles and drift eliminators; check fan performance.",
      "Confirm the clean baseline approach is correct for this plant."),
    T("range", "high", "High heat load or low circulating flow.",
      "Check circulating flow and process load.", "Verify temperature sensors."),
    T("dp", "high", "Filter loading with solids.",
      "Backwash the side-stream filter; review chemistry if loading is fast.",
      "Do not exceed the filter's maximum differential pressure."),
    T("rem", "low", "Filter breakthrough, damaged media/screen or bypass.",
      "Inspect screen/media for damage or bypass; backwash.",
      "Poor filtration increases fouling in the tower."),
]  # fmt: skip


CHEM_FILTER = "['tds', 'sio2', 'mic', 'cond']"
CHEM_THERMAL = "['lsi', 'hard', 'alk', 'mic']"
FILTER_PROBABILITY = f"min(95, 15 + 22 * count_off({CHEM_FILTER}) + sev('dp') + sev('rem'))"
THERMAL_PROBABILITY = f"min(95, 15 + 20 * count_off({CHEM_THERMAL}) + sev('resid') + sev('appr'))"

R = TemplateRule

# Demo heuristics. FLT-P03 vs FLT-P01 follow the original spec: chemistry influence present →
# faster loading (P03); ΔP off without chemistry influence → normal loading (P01).
RULES = [
    R("FLT-P01", "Normal filter loading", f"off('dp') and count_off({CHEM_FILTER}) == 0",
      FILTER_PROBABILITY, "Schedule the next backwash.", ("filter",)),
    R("FLT-P02", "Breakthrough / poor removal", "off('rem')",
      FILTER_PROBABILITY, "Inspect screen or media for damage or bypass.", ("filter",)),
    R("FLT-P03", "Faster loading than normal", f"count_off({CHEM_FILTER}) > 0",
      FILTER_PROBABILITY, "Backwash earlier and review chemistry limits.", ("filter",)),
    R("TH-P01", "Thermal performance deterioration",
      f"(off('resid') or off('appr')) and count_off({CHEM_THERMAL}) == 0 and not off('dp')",
      THERMAL_PROBABILITY, "Check fan, airflow and process load.", ("thermal",)),
    R("TH-P02", "Fouling / solids deposition",
      f"(off('resid') or off('appr') or count_off({CHEM_THERMAL}) > 0)"
      f" and (count_off({CHEM_THERMAL}) > 0 or off('dp'))",
      THERMAL_PROBABILITY, "Increase side-stream filtration; inspect fill and nozzles.",
      ("thermal",)),
]  # fmt: skip


MODULES = [
    TemplateModule(
        "water_chemistry",
        "Water Chemistry",
        [
            {"type": "alert_list", "title": "Alerts"},
            {"type": "input_group", "title": "Chemistry", "group": "chemistry"},
            {"type": "input_group", "title": "Thermal", "group": "thermal"},
            {"type": "input_group", "title": "Filter", "group": "filter"},
            {
                "type": "value_tiles",
                "title": "Calculated values",
                "params": ["lsi", "range", "appr", "heat", "resid", "dp", "rem", "bw"],
            },
        ],
    ),
    TemplateModule(
        "filter",
        "Filter",
        [
            {"type": "value_tiles", "title": "Filter KPIs", "params": ["dp", "rem", "bw"]},
            {
                "type": "inputs_summary",
                "title": "Inputs used",
                "params": ["pin", "pout", "tin", "tout", "bwf", "bwt"],
            },
            {
                "type": "predicted_problems",
                "title": "Predicted problems",
                "rules": ["FLT-P01", "FLT-P02", "FLT-P03"],
            },
        ],
    ),
    TemplateModule(
        "thermal",
        "Thermal",
        [
            {
                "type": "value_tiles",
                "title": "Thermal KPIs",
                "params": ["appr", "range", "heat", "resid"],
            },
            {
                "type": "inputs_summary",
                "title": "Inputs used",
                "params": ["ts", "tr", "wbt", "flow", "fan"],
            },
            {
                "type": "text_note",
                "text": "Approach residual compares today's approach with the plant's clean "
                "baseline approach, set by the manager.",
            },
            {
                "type": "predicted_problems",
                "title": "Predicted problems",
                "rules": ["TH-P01", "TH-P02"],
            },
        ],
    ),
]


DEFAULT_TEMPLATE = Template(
    key="default",
    name="SMAYAA standard (Water Chemistry, Filter, Thermal)",
    parameters=PARAMETERS,
    treatments=TREATMENTS,
    rules=RULES,
    modules=MODULES,
    plant_setting_defaults={"clean_baseline_approach": 4.0},
)

TEMPLATES = {DEFAULT_TEMPLATE.key: DEFAULT_TEMPLATE}
