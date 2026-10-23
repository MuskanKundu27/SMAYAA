"""The default SMAYAA template: Input Parameters (data entry), Side-Stream Filtration and
Thermal Efficiency.

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

# Inputs and KPIs follow the engineering note (Thermal Efficiency and Side-Stream Filtration
# modules). Optional inputs have no limits; KPIs that need them show "No data" until they exist.
# Trend KPIs use the time functions (engine/history.py) and need some history first.
PARAMETERS = [
    # Chemistry (typed in)
    P("ph", "pH", "", "chemistry", 7.9, (6.8, 7.2, 8.2, 8.8)),
    P("cond", "Conductivity", "µS/cm", "chemistry", 2400, (800, 1200, 2800, 3400), precision=0),
    P("tds", "TDS", "ppm", "chemistry", 1500, (500, 800, 1800, 2200), precision=0),
    P("hard", "Hardness", "ppm", "chemistry", 650, (100, 200, 600, 800), precision=0),
    P("alk", "Alkalinity", "ppm", "chemistry", 300, (100, 150, 350, 450), precision=0),
    P("sio2", "Silica", "ppm", "chemistry", 95, (0, 0, 120, 150), precision=0),
    P("mic", "Microbial count", "CFU/mL", "chemistry", 600, (0, 0, 1000, 5000), precision=0),
    # Thermal (typed in or from the plant system)
    P("ts", "Supply temperature", "°C", "thermal", 31, (20, 25, 32, 35), precision=1),
    P("tr", "Return temperature", "°C", "thermal", 39, (30, 35, 42, 45), precision=1),
    P("wbt", "Wet-bulb temperature", "°C", "thermal", 26, precision=1),
    P("flow", "Circulating flow", "m³/h", "thermal", 1000, (500, 700, 1300, 1500), precision=0),
    P("fan", "Fan power", "kW", "thermal", 70, (0, 0, 80, 95), precision=1),
    P("fanspd", "Fan speed", "%", "thermal", 100, precision=0),
    P("pumpspd", "Pump speed", "%", "thermal", 100, precision=0),
    P("pumppow", "Pump power", "kW", "thermal", 55, precision=1),
    P("pumpp", "Pump discharge pressure", "bar", "thermal", 2.8),
    P("load", "Process load", "%", "thermal", 100, precision=0),
    # Side-stream filter (typed in or from the plant system)
    P("pin", "Inlet pressure", "bar", "filter", 2.4),
    P("pout", "Outlet pressure", "bar", "filter", 1.8),
    P("ssflow", "Side-stream flow", "m³/h", "filter", 50, precision=1),
    P("tin", "Inlet turbidity", "NTU", "filter", 12, precision=1),
    P("tout", "Outlet turbidity", "NTU", "filter", 2, precision=1),
    P("tssin", "Inlet TSS", "mg/L", "filter", 15, precision=1),
    P("tssout", "Outlet TSS", "mg/L", "filter", 3, precision=1),
    P("clean", "Cleaning / backwash active", "", "indication", 0, precision=0),
    P("bwf", "Backwash flow", "m³/h", "filter", 30, precision=1),
    P("bwt", "Backwash time", "min", "indication", 6, precision=1),
    P("oil", "Oil in water", "mg/L", "filter", 0, precision=1),
    P("valve", "Bypass valve open", "", "indication", 0, precision=0),
    P("sspump", "Side-stream pump running", "", "indication", 1, precision=0),
    # Calculated: chemistry
    P("lsi", "LSI (demo formula)", "", "chemistry", limits=(-1, -0.5, 0.8, 1.5),
      formula="ph - 7.6 + (hard - 400) / 800 + (alk - 250) / 600"),
    # Calculated: thermal efficiency KPIs
    P("range", "Range", "°C", "thermal", limits=(3, 5, 10, 12), formula="tr - ts", precision=1),
    P("appr", "Approach", "°C", "thermal", limits=(2, 3, 6, 8), formula="ts - wbt", precision=1),
    P("heat", "Heat load", "kW", "thermal", formula="1.163 * flow * (tr - ts)", precision=0),
    # Expected approach = model(WBT, heat load, flow, fan speed, clean baseline) per the note.
    # Demo model until a calibrated one exists: the clean baseline scaled for duty (process load
    # proxy if available, else heat load vs design), fan speed, flow vs design and wet-bulb vs
    # design. Design values are plant settings.
    P("expappr", "Expected approach (demo model)", "°C", "thermal",
      formula="base * coalesce(load / 100, heat / setting('design_heat_load')) ** 0.7"
              " * (100 / max(coalesce(fanspd, 100), 20)) ** 0.5"
              " * (flow / setting('design_flow')) ** 0.2"
              " * (1 + 0.02 * (setting('design_wbt') - wbt))", precision=1),
    P("resid", "Approach residual", "°C", "thermal", limits=(-2, -2, 1.5, 3),
      formula="appr - expappr", precision=1),
    # ΔApproach / ΔFan speed, or / ΔFan power when speed is not measured.
    P("fanresp", "Fan response (6 h)", "°C per % (or kW)", "thermal",
      formula="coalesce(change('appr', 6) / change('fanspd', 6),"
              " change('appr', 6) / change('fan', 6))", precision=3),
    P("sfe", "Specific fan energy", "kW per MW", "thermal", formula="fan / heat * 1000",
      precision=1),
    # Calculated: side-stream filtration KPIs
    P("dp", "Filter ΔP", "bar", "filter", limits=(0, 0, 0.8, 1.2), formula="pin - pout"),
    P("rem", "Removal efficiency", "%", "filter", limits=(50, 70, 100, 100),
      formula="(tin - tout) / tin * 100", precision=1),
    P("dprate", "ΔP rate of change", "bar/day", "filter", formula="rate('dp', 24) * 24",
      precision=3),
    P("solids", "Solids load proxy", "kg/h", "filter",
      formula="ssflow * coalesce(tssin, tin) / 1000", precision=2),
    P("cleancount", "Cleanings (7 days)", "", "filter", formula="events('clean', 168)",
      precision=0),
    # Time between valid cleaning events: the last two cleanings.
    P("cleanint", "Cleaning interval", "h", "filter", formula="event_interval('clean')",
      precision=0),
    P("dprec", "ΔP recovery (last cleaning)", "bar", "filter",
      formula="before_event('dp', 'clean') - after_event('dp', 'clean')"),
    P("bw", "Water per cleaning", "m³", "filter", formula="bwf * bwt / 60", precision=1),
    P("treated", "m³ treated per cleaning (7 days)", "m³", "filter",
      formula="total('ssflow', 168) / events('clean', 168)", precision=0),
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
# Trend pieces. coalesce(..., 0) means "no trend yet counts as no change", so a rule can still
# decide from today's values; rules that only make sense with a trend leave it out and show
# "insufficient data" until there is enough history.
RESID_TREND = "coalesce(rate('resid', 24) * 24, 0)"  # °C per day
STABLE_CONDITIONS = (
    "abs(coalesce(change('wbt', 24), 0)) < 2 and abs(coalesce(change('load', 24), 0)) < 10"
)

R = TemplateRule

# Predicted problems from the engineering note. Conditions and probabilities are demo
# heuristics until trained models take over the same codes.
RULES = [
    # --- Side-stream filtration ---
    R("FLT-P01", "Normal loading / time to clean",
      f"(off('dp') or coalesce(dprate, 0) > 0) and not off('rem')"
      f" and count_off({CHEM_FILTER}) == 0",
      FILTER_PROBABILITY, "Schedule the next backwash (see time to clean).", ("filter",)),
    R("FLT-P02", "Breakthrough / poor removal",
      "off('rem') or (coalesce(rate('tout', 24), 0) > 0.5 and coalesce(rate('rem', 24), 0) < 0)",
      FILTER_PROBABILITY, "Inspect screen or media for damage, channeling or bypass.",
      ("filter",)),
    R("FLT-P03", "Abnormally fast loading",
      f"count_off({CHEM_FILTER}) > 0"
      " or (coalesce(dprate, 0) > 0.2 and coalesce(rate('tin', 24), 0) > 0)"
      " or coalesce(oil, 0) > 5",
      FILTER_PROBABILITY, "Backwash earlier; look for a contamination event or high solids.",
      ("filter",)),
    R("FLT-P04", "Low flow / hydraulic restriction",
      "(off('dp') and rate('ssflow', 24) < 0) or coalesce(sspump, 1) < 0.5",
      "min(95, 30 + sev('dp'))", "Check strainer, pump and valves on the side-stream line.",
      ("filter",)),
    R("FLT-P05", "Ineffective cleaning",
      "dprec < 0.15 or after_event('dp', 'clean') > setting('clean_dp_baseline') + 0.2",
      "min(95, 40 + sev('dp') + min(20, 4 * coalesce(oil, 0)))",
      "Check backwash sequence and filter internals; check for oil fouling.", ("filter",)),
    R("FLT-P06", "Excessive cleaning water",
      "(events('clean', 168) > 7 or bw > 1.5 * setting('min_water_per_clean'))"
      " and not off('rem')",
      "min(95, 20 + 5 * coalesce(events('clean', 168), 0))",
      "Review the backwash trigger and sequence; save water.", ("filter",)),
    R("FLT-P07", "Low ΔP with high outlet turbidity",
      "(dp < 0.2 and (off('rem') or tout > 5)) or coalesce(valve, 0) >= 0.5",
      "min(95, 40 + sev('rem'))", "Check for an open bypass, channeling or a damaged element.",
      ("filter",)),
    # --- Thermal efficiency ---
    R("TH-P01", "Thermal performance deterioration",
      f"(off('resid') or {RESID_TREND} > 0.3) and {STABLE_CONDITIONS}"
      f" and count_off({CHEM_THERMAL}) == 0 and not off('dp')",
      f"min(95, 25 + sev('resid') + sev('appr') + min(30, 60 * max(0, {RESID_TREND})))",
      "Check fan, airflow and process load.", ("thermal",)),
    R("TH-P02", "Fouling / solids deposition",
      f"(off('resid') or off('appr') or count_off({CHEM_THERMAL}) > 0 or {RESID_TREND} > 0)"
      f" and (count_off({CHEM_THERMAL}) > 0 or off('dp')"
      " or coalesce(rate('tssin', 24), 0) > 0 or coalesce(dprate, 0) > 0.1)",
      THERMAL_PROBABILITY, "Increase side-stream filtration; inspect fill and nozzles.",
      ("thermal", "filter")),
    R("TH-P03", "Airflow / fan underperformance",
      "off('resid') and (rate('fan', 24) > 0 or rate('fanspd', 24) > 0)"
      " and coalesce(fanresp, 0) > -0.01",
      "min(95, 30 + sev('resid') + sev('fan'))",
      "Inspect fan, belt/gearbox, louvers; check for recirculation or a blocked air path.",
      ("thermal",)),
    R("TH-P04", "Hydraulic restriction / low circulation",
      "rate('flow', 24) < 0 and rate('range', 24) > 0"
      " and (abs(coalesce(rate('pumpp', 24), 0)) > 0 or off('flow'))",
      "min(95, 30 + sev('flow') + sev('range'))",
      "Check strainers, valves and pumps; look for a process restriction.", ("thermal",)),
    R("TH-P05", "Excess circulation / bypass / sensor mismatch",
      "rate('range', 24) < 0 and abs(coalesce(change('load', 24), 0)) < 5",
      "min(95, 25 + sev('range'))",
      "Check for an open bypass, excess pump speed, or temperature/flow sensor errors.",
      ("thermal",)),
    R("TH-P06", "Thermal energy inefficiency",
      "rate('sfe', 24) > 0 and coalesce(rate('heat', 24), 0) <= 0",
      "min(95, 30 + sev('fan'))",
      "Look for airflow restriction, hydraulic inefficiency or fouling.", ("thermal",)),
]  # fmt: skip


FILTER_RULES = ["FLT-P01", "FLT-P02", "FLT-P03", "FLT-P04", "FLT-P05", "FLT-P06", "FLT-P07"]
THERMAL_RULES = ["TH-P01", "TH-P02", "TH-P03", "TH-P04", "TH-P05", "TH-P06"]

MODULES = [
    TemplateModule(
        "water_chemistry",
        "Input Parameters",
        [
            {"type": "input_group", "title": "Chemistry", "group": "chemistry"},
            {"type": "input_group", "title": "Thermal", "group": "thermal"},
            {"type": "input_group", "title": "Side-stream filter", "group": "filter"},
            {
                "type": "input_group",
                "title": "Indication",
                "params": ["clean", "valve", "sspump", "bwt"],
                "switches": ["clean", "valve", "sspump"],
            },
            {
                "type": "value_tiles",
                "title": "Calculated values",
                "params": ["lsi", "range", "appr", "resid", "heat", "dp", "rem", "bw"],
            },
        ],
    ),
    TemplateModule(
        "filter",
        "Side-Stream Filtration",
        [
            {
                "type": "value_tiles",
                "title": "Filtration KPIs",
                "params": ["dp", "rem", "dprate", "solids"],
            },
            {
                "type": "value_tiles",
                "title": "Cleaning",
                "params": ["cleancount", "cleanint", "dprec", "bw", "treated"],
            },
            {"type": "trend_chart", "title": "Filter ΔP (7 days)", "params": ["dp"], "hours": 168},
            {
                "type": "inputs_summary",
                "title": "Inputs used",
                "params": ["pin", "pout", "ssflow", "tin", "tout", "tssin", "tssout", "clean",
                           "bwf", "bwt", "oil", "valve", "sspump"],
            },
            {"type": "predicted_problems", "title": "Predicted problems", "rules": FILTER_RULES},
            {
                "type": "text_note",
                "text": "Trend KPIs (rate of change, forecasts, cleaning interval, ΔP recovery) "
                "need a few readings over time before they show a value.",
            },
        ],
    ),
    TemplateModule(
        "thermal",
        "Thermal Efficiency",
        [
            {
                "type": "value_tiles",
                "title": "Thermal KPIs",
                "params": ["appr", "expappr", "resid", "range", "heat", "fanresp", "sfe"],
            },
            {
                "type": "trend_chart",
                "title": "Approach and residual (7 days)",
                "params": ["appr", "resid"],
                "hours": 168,
            },
            {
                "type": "inputs_summary",
                "title": "Inputs used",
                "params": ["ts", "tr", "wbt", "flow", "fan", "fanspd", "pumpspd", "pumppow",
                           "pumpp", "load", "tin", "tssin"],
            },
            {"type": "predicted_problems", "title": "Predicted problems", "rules": THERMAL_RULES},
            {
                "type": "text_note",
                "text": "Expected approach is a demo model: the plant's clean baseline approach "
                "scaled for heat load (or process load), fan speed, flow and wet-bulb against "
                "the plant's design values. Approach residual = actual minus expected.",
            },
        ],
    ),
]  # fmt: skip


DEFAULT_TEMPLATE = Template(
    key="default",
    name="SMAYAA standard (Input Parameters, Side-Stream Filtration, Thermal Efficiency)",
    parameters=PARAMETERS,
    treatments=TREATMENTS,
    rules=RULES,
    modules=MODULES,
    # Plant settings (each plant may override): design values and thresholds used by formulas
    # through setting('name').
    plant_setting_defaults={
        "clean_baseline_approach": 4.0,
        "design_heat_load": 9304.0,
        "design_flow": 1000.0,
        "design_wbt": 26.0,
        "clean_dp_baseline": 0.2,
        "min_water_per_clean": 2.5,
    },
)

TEMPLATES = {DEFAULT_TEMPLATE.key: DEFAULT_TEMPLATE}
