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
    # measured=True: has a formula but starts as measured (typed in or from a PLC); the super
    # admin can switch it to calculated per company.
    measured: bool = False
    active: bool = True

    @property
    def kind(self) -> str:
        return "calculated" if self.formula and not self.measured else "input"


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
    priority: str = "medium"  # high | medium | low (severity / action priority)
    benefit: str = ""  # expected benefit of the recommended action
    eta: str | None = None  # hours until the problem is expected


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
    # ORP: no default limits; the manager sets the plant's range with the treatment supplier
    # (chlorine programmes often run 400-600 mV).
    P("orp", "ORP", "mV", "chemistry", 650, precision=0),
    # Make-up, blowdown and dosing (Instrument Index: AIT-EC-MU, FT-MU, FT-BD, CHEM-FB)
    P("mucond", "Make-up conductivity", "µS/cm", "coc", 480, precision=0),
    P("muflow", "Make-up flow", "m³/h", "coc", 15.0, precision=1),
    P("bdflow", "Blowdown flow", "m³/h", "coc", 3.4),
    P("chemdose", "Chemical dosing flow", "L/h", "coc", 2.35),
    # Water balance (engineering workbook "Plant Inputs" / "Water Balance"; the plant reuses water)
    P("rwflow", "Recycled water flow", "m³/h", "water", 3.0, precision=1),
    P("otherloss", "Backwash / other loss", "m³/h", "water", 0.3),
    P("storage", "Storage change (+ = filling)", "m³/h", "water", 0.0),
    # Thermal (typed in or from the plant system)
    P("ts", "Supply temperature", "°C", "thermal", 31, (20, 25, 32, 35), precision=1),
    P("tr", "Return temperature", "°C", "thermal", 39, (30, 35, 42, 45), precision=1),
    P("wbt", "Wet-bulb temperature", "°C", "thermal", 26, precision=1),
    P("flow", "Circulating flow", "m³/h", "thermal", 1000, (500, 700, 1300, 1500), precision=0),
    # Fan power: measured by a kW meter, or calculated from voltage, current and power factor
    # (P = sqrt(3) x V x I x PF / 1000). The three inputs switch on when it is set to calculated.
    P("fan", "Fan power", "kW", "thermal", 70, (0, 0, 80, 95), precision=1,
      formula="sqrt(3) * fanv * fani * fanpf / 1000", measured=True),
    P("fanv", "Fan voltage (line to line)", "V", "thermal", 415, precision=0, active=False),
    P("fani", "Fan current (line)", "A", "thermal", 115, precision=1, active=False),
    P("fanpf", "Fan motor power factor", "", "thermal", 0.85, active=False),
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
    P("bdvalve", "Blowdown valve open", "", "indication", 1, precision=0),
    # Calculated: chemistry
    # LSI = pH - pHs, pHs = (9.3 + A + B) - (C + D); A = (log10(TDS) - 1) / 10,
    # B = -13.12 log10(T + 273.15) + 34 (T = return temperature, the hottest water),
    # C = log10(total hardness) - 0.4, D = log10(alkalinity). Limits: 0 to 1.5 good (slightly
    # scale-forming, held by inhibitor), below 0 corrosive, above 2.5 = common upper ceiling.
    P("lsi", "LSI (Langelier Saturation Index)", "", "chemistry", limits=(-0.5, 0, 1.5, 2.5),
      formula="ph - ((9.3 + (log10(tds) - 1) / 10 + (34 - 13.12 * log10(tr + 273.15)))"
              " - ((log10(hard) - 0.4) + log10(alk)))"),
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
    # Calculated: CoC & Blowdown (engineering workbook "CoC & Blowdown" sheet and the Cause &
    # Effect Matrix KPI library). Targets and baselines are plant settings.
    # No default limits: the manager sets the plant's CoC range on the Limits page.
    P("coc", "Cycles of concentration", "", "coc", formula="cond / mucond", precision=1),
    # Flow-based CoC includes drift (KPI-17: "flow CoC should include evaporation/drift").
    # Workbook "CoC by Flow - improved": water in / (blowdown + drift + other concentrated
    # losses); water in includes recycled water.
    P("cocflow", "CoC by flow", "", "coc",
      formula="(muflow + coalesce(rwflow, 0))"
              " / (bdflow + setting('drift_loss') + coalesce(otherloss, 0))", precision=1),
    P("cocmis", "CoC mismatch (conductivity vs flow)", "%", "coc", limits=(0, 0, 10, 20),
      formula="abs(coc - cocflow) / coc * 100", precision=1),
    # Water-side evaporation: heat load / latent heat (h_fg = 2501 - 2.361 x mean water temp).
    P("evap", "Evaporation", "m³/h", "coc",
      formula="heat * 3600 / ((2501 - 2.361 * (tr + ts) / 2) * 1000)"),
    P("condsp", "Conductivity setpoint", "µS/cm", "coc",
      formula="mucond * setting('target_coc')", precision=0),
    # High warning about 5 % above the setpoint, high-high alarm about 10 % (Setpoint Builder).
    P("condvsp", "Conductivity vs setpoint", "%", "coc", limits=(-100, -100, 5, 10),
      formula="(cond - condsp) / condsp * 100", precision=1),
    # Theoretical blowdown = E / (target CoC - 1) - drift, never negative (KPI-09).
    P("bdreq", "Required blowdown", "m³/h", "coc",
      formula="max(0, evap / (setting('target_coc') - 1) - setting('drift_loss'))"),
    P("bddev", "Blowdown vs required", "%", "coc", limits=(-25, -10, 10, 25),
      formula="(bdflow - bdreq) / bdreq * 100", precision=1),
    # Benefits against the plant's baseline (before optimisation), set by the manager.
    P("bdlower", "Blowdown reduction vs baseline", "%", "coc",
      formula="(setting('baseline_blowdown') - bdflow) / setting('baseline_blowdown') * 100",
      precision=0),
    P("mulower", "Water use reduction vs baseline", "%", "coc",
      formula="(setting('baseline_makeup') - muflow) / setting('baseline_makeup') * 100",
      precision=0),
    # Uses the 24 h average make-up when there is enough history, else the latest value.
    P("watersaved", "Water saved (24 h)", "m³", "coc",
      formula="(setting('baseline_makeup') - coalesce(avg('muflow', 24), muflow)) * 24",
      precision=0),
    P("costsaved", "Water cost saved (24 h)", "₹", "coc",
      formula="watersaved * setting('water_cost')", precision=0),
    P("chemvt", "Chemical use vs target", "%", "coc",
      formula="(chemdose - setting('chem_target')) / setting('chem_target') * 100", precision=0),
    # Calculated: water balance (engineering workbook "Water Balance", "Cooling Tower",
    # "Energy & Cost" and "Dashboard" sheets). Missing recycled / other loss / storage count as 0.
    P("totalin", "Total water in", "m³/h", "water",
      formula="muflow + coalesce(rwflow, 0)", precision=1),
    P("explained", "Explained losses", "m³/h", "water",
      formula="evap + bdflow + setting('drift_loss') + coalesce(otherloss, 0)"
              " + coalesce(storage, 0)"),
    P("unacc", "Unaccounted water", "m³/h", "water", formula="totalin - explained"),
    # Workbook: good within ±5 %; Diagnostic Engine: warning above 5 %, critical above 15 %.
    P("wberr", "Water balance error", "%", "water", limits=(-15, -5, 5, 15),
      formula="unacc / totalin * 100", precision=1),
    P("expmu", "Expected make-up", "m³/h", "water",
      formula="evap + setting('design_blowdown') + setting('drift_loss')"
              " + setting('design_other_loss') + setting('design_storage_change')"
              " - coalesce(rwflow, 0)", precision=1),
    P("mudev", "Make-up deviation", "%", "water", limits=(-15, -5, 5, 15),
      formula="(muflow - expmu) / expmu * 100", precision=1),
    P("evappct", "Evaporation share of water in", "%", "water",
      formula="evap / totalin * 100", precision=0),
    P("recshare", "Recycled share of water in", "%", "water",
      formula="coalesce(rwflow, 0) / totalin * 100", precision=0),
    P("discharge", "Discharge (blowdown + other loss)", "m³/h", "water",
      formula="bdflow + coalesce(otherloss, 0)"),
    # Dashboard "Water Efficiency" score = 100 - 3 x |water balance error|.
    P("wbhealth", "Water efficiency score", "%", "water", limits=(50, 70, 100, 100),
      formula="max(0, 100 - 3 * abs(wberr))", precision=0),
    # Energy & Cost: excess make-up (above expected) x water / chemical cost, here per 24 h.
    P("excesswater", "Excess make-up water (24 h)", "m³", "water",
      formula="max(0, muflow - expmu) * 24", precision=0),
    P("excesscost", "Excess water + chemical cost (24 h)", "₹", "water",
      formula="excesswater * (setting('water_cost') + setting('chemical_cost'))", precision=0),
    # Change since about 24 h ago (the design's "vs yesterday").
    P("muvsyday", "Make-up vs yesterday", "%", "water",
      formula="change('muflow', 24) / (muflow - change('muflow', 24)) * 100", precision=0),
    P("rwvsyday", "Recycled water vs yesterday", "%", "water",
      formula="change('rwflow', 24) / (rwflow - change('rwflow', 24)) * 100", precision=0),
    P("bdvsyday", "Blowdown vs yesterday", "%", "water",
      formula="change('bdflow', 24) / (bdflow - change('bdflow', 24)) * 100", precision=0),
    P("evapvsyday", "Evaporation vs yesterday", "%", "water",
      formula="change('evap', 24) / (evap - change('evap', 24)) * 100", precision=0),
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
    T("orp", "low", "Biocide underfeed, high biological demand or a failed dosing pump.",
      "Check chemical stock, dosing pump, injection point and mixing; restore biocide feed.",
      "Low ORP raises biological growth and Legionella risk."),
    T("orp", "high", "Oxidising biocide overdosing.",
      "Reduce biocide dose; validate the ORP analyser against a lab test.",
      "High oxidant levels increase corrosion of carbon steel and copper."),
    T("coc", "high", "Too little blowdown, controller setpoint too high or make-up quality change.",
      "Increase blowdown; check the conductivity controller, probe calibration and setpoint.",
      "High cycles raise scaling risk; confirm the treatment programme's CoC limit."),
    T("coc", "low", "Excess blowdown, passing blowdown valve, leak or overflow.",
      "Reduce blowdown towards the required rate; inspect the blowdown valve and overflow.",
      "Low cycles waste water and treatment chemicals."),
    T("cocmis", "high", "Meter error, unmetered losses (overflow, leak, drift) or contamination.",
      "Validate conductivity and flow meters; inspect overflow, drains and leaks.",
      "Do not raise CoC until the methods agree again."),
    T("condvsp", "high", "Insufficient blowdown or rapid concentration.",
      "Verify the blowdown valve and meter; start a controlled blowdown.",
      "Protect basin level while increasing blowdown."),
    T("bddev", "high", "Blowdown above the rate needed for the target CoC.",
      "Reduce blowdown; check controller setpoint and for a passing valve.",
      "Change setpoints in small steps and watch conductivity."),
    T("wberr", "high", "Leak, overflow, drain, storage change or meter error.",
      "Check basin overflow, drains, leaks and flowmeter calibration.",
      "Persistent error should be investigated; confirm meters before changing setpoints."),
    T("wberr", "low", "More losses than water in: meter error or an unrecorded water source.",
      "Check make-up and recycled-water meters and the evaporation estimate.",
      "Do not trust savings figures until the balance closes."),
    T("mudev", "high", "Make-up above expected: water loss, storage change or meter error.",
      "Investigate water loss, storage and the make-up meter; review blowdown.",
      "Excess make-up raises water and chemical cost."),
    T("mudev", "low", "Make-up below expected: blowdown too low or a meter error.",
      "Check blowdown and conductivity; verify the make-up meter.",
      "Low make-up with rising conductivity means scaling risk."),
    T("bddev", "low", "Blowdown below the rate needed for the target CoC.",
      "Increase blowdown; check the blowdown valve and line for blockage.",
      "Conductivity and scaling risk will rise if blowdown stays low."),
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
COC_CHEMISTRY_OK = "count_off(['lsi', 'ph', 'hard', 'alk', 'sio2', 'orp']) == 0"
COND_RATE = "rate('cond', 6)"  # µS/cm per hour over the last 6 h

# Predicted problems from the engineering note. Conditions and probabilities are demo
# heuristics until trained models take over the same codes.
RULES = [
    # --- Side-stream filtration ---
    R("FLT-P01", "Normal loading / time to clean",
      f"(off('dp') or coalesce(dprate, 0) > 0) and not off('rem')"
      f" and count_off({CHEM_FILTER}) == 0",
      FILTER_PROBABILITY, "Schedule the next backwash (see time to clean).", ("filter",),
      priority="medium", benefit="Keep the filter available · plan cleaning"),
    R("FLT-P02", "Breakthrough / poor removal",
      "off('rem') or (coalesce(rate('tout', 24), 0) > 0.5 and coalesce(rate('rem', 24), 0) < 0)",
      FILTER_PROBABILITY, "Inspect screen or media for damage, channeling or bypass.",
      ("filter",),
      priority="high", benefit="Restore filtered-water quality"),
    R("FLT-P03", "Abnormally fast loading",
      f"count_off({CHEM_FILTER}) > 0"
      " or (coalesce(dprate, 0) > 0.2 and coalesce(rate('tin', 24), 0) > 0)"
      " or coalesce(oil, 0) > 5",
      FILTER_PROBABILITY, "Backwash earlier; look for a contamination event or high solids.",
      ("filter",),
      priority="medium", benefit="Protect the tower from solids · fewer cleanings"),
    R("FLT-P04", "Low flow / hydraulic restriction",
      "(off('dp') and rate('ssflow', 24) < 0) or coalesce(sspump, 1) < 0.5",
      "min(95, 30 + sev('dp'))", "Check strainer, pump and valves on the side-stream line.",
      ("filter",),
      priority="medium", benefit="Restore side-stream flow"),
    R("FLT-P05", "Ineffective cleaning",
      "dprec < 0.15 or after_event('dp', 'clean') > setting('clean_dp_baseline') + 0.2",
      "min(95, 40 + sev('dp') + min(20, 4 * coalesce(oil, 0)))",
      "Check backwash sequence and filter internals; check for oil fouling.", ("filter",),
      priority="medium", benefit="Recover ΔP · extend filter life"),
    R("FLT-P06", "Excessive cleaning water",
      "(events('clean', 168) > 7 or bw > 1.5 * setting('min_water_per_clean'))"
      " and not off('rem')",
      "min(95, 20 + 5 * coalesce(events('clean', 168), 0))",
      "Review the backwash trigger and sequence; save water.", ("filter",),
      priority="medium", benefit="Save backwash water"),
    R("FLT-P07", "Low ΔP with high outlet turbidity",
      "(dp < 0.2 and (off('rem') or tout > 5)) or coalesce(valve, 0) >= 0.5",
      "min(95, 40 + sev('rem'))", "Check for an open bypass, channeling or a damaged element.",
      ("filter",),
      priority="high", benefit="Stop bypass · restore removal"),
    # --- Thermal efficiency ---
    R("TH-P01", "Thermal performance deterioration",
      f"(off('resid') or {RESID_TREND} > 0.3) and {STABLE_CONDITIONS}"
      f" and count_off({CHEM_THERMAL}) == 0 and not off('dp')",
      f"min(95, 25 + sev('resid') + sev('appr') + min(30, 60 * max(0, {RESID_TREND})))",
      "Check fan, airflow and process load.", ("thermal",),
      priority="high", benefit="Recover cooling capacity"),
    R("TH-P02", "Fouling / solids deposition",
      f"(off('resid') or off('appr') or count_off({CHEM_THERMAL}) > 0 or {RESID_TREND} > 0)"
      f" and (count_off({CHEM_THERMAL}) > 0 or off('dp')"
      " or coalesce(rate('tssin', 24), 0) > 0 or coalesce(dprate, 0) > 0.1)",
      THERMAL_PROBABILITY, "Increase side-stream filtration; inspect fill and nozzles.",
      ("thermal", "filter"),
      priority="high", benefit="Restore heat transfer · prevent fouling"),
    R("TH-P03", "Airflow / fan underperformance",
      "off('resid') and (rate('fan', 24) > 0 or rate('fanspd', 24) > 0)"
      " and coalesce(fanresp, 0) > -0.01",
      "min(95, 30 + sev('resid') + sev('fan'))",
      "Inspect fan, belt/gearbox, louvers; check for recirculation or a blocked air path.",
      ("thermal",),
      priority="high", benefit="Recover airflow · save fan energy"),
    R("TH-P04", "Hydraulic restriction / low circulation",
      "rate('flow', 24) < 0 and rate('range', 24) > 0"
      " and (abs(coalesce(rate('pumpp', 24), 0)) > 0 or off('flow'))",
      "min(95, 30 + sev('flow') + sev('range'))",
      "Check strainers, valves and pumps; look for a process restriction.", ("thermal",),
      priority="high", benefit="Restore circulation and cooling"),
    R("TH-P05", "Excess circulation / bypass / sensor mismatch",
      "rate('range', 24) < 0 and abs(coalesce(change('load', 24), 0)) < 5",
      "min(95, 25 + sev('range'))",
      "Check for an open bypass, excess pump speed, or temperature/flow sensor errors.",
      ("thermal",),
      priority="medium", benefit="Save pump energy · fix sensors"),
    R("TH-P06", "Thermal energy inefficiency",
      "rate('sfe', 24) > 0 and coalesce(rate('heat', 24), 0) <= 0",
      "min(95, 30 + sev('fan'))",
      "Look for airflow restriction, hydraulic inefficiency or fouling.", ("thermal",),
      priority="medium", benefit="Reduce fan energy"),
    # --- CoC & Blowdown (Cause & Effect Matrix COC-01..03, WB-03, WB-04, SC-01, BIO-01/02) ---
    R("COC-P01", "Excessive blowdown",
      "high('bddev')",
      "min(95, 40 + sev('bddev') + sev('coc'))",
      "Adjust blowdown to maintain CoC: reduce towards the required rate and check the"
      " conductivity controller setpoint.", ("coc",), priority="high",
      benefit="Maintain optimal CoC · save water"),
    R("COC-P02", "Rising conductivity",
      f"high('condvsp') or (coalesce({COND_RATE}, 0) > 0 and condvsp > -5)",
      f"min(95, 30 + sev('condvsp') + if_else(coalesce({COND_RATE}, 0) > 0, 25, 0))",
      "Review the conductivity setpoint; verify the blowdown valve and meter and start a"
      " controlled blowdown.", ("coc",), priority="high",
      benefit="Prevent scaling · protect assets"),
    R("COC-P03", "Scaling risk increasing",
      "(high('lsi') or coalesce(rate('lsi', 24), 0) * 24 > 0.1)"
      " and (high('coc') or high('hard') or high('alk') or high('ph'))",
      "min(95, 25 + sev('lsi') + 10 * count_off(['coc', 'hard', 'alk', 'ph']))",
      "Lower CoC (increase blowdown); verify scale-inhibitor and acid dosing.",
      ("coc", "thermal"), priority="high", benefit="Protect heat transfer · avoid scale"),
    R("COC-P04", "Blowdown valve leakage",
      "coalesce(bdvalve, 1) < 0.5 and bdflow > 0.1",
      "min(95, 45 + min(40, 10 * bdflow))",
      "Inspect the blowdown valve and piping; repair a passing valve or closed bypass.",
      ("coc",), priority="medium", benefit="Prevent water loss · improve efficiency"),
    R("COC-P05", "Conductivity rising with blowdown valve open",
      f"coalesce(bdvalve, 0) >= 0.5 and coalesce({COND_RATE}, 0) > 0 and condvsp > 0",
      "min(95, 35 + sev('condvsp'))",
      "Inspect the blowdown valve and line for blockage; check make-up water quality.",
      ("coc",), priority="high", benefit="Restore conductivity control"),
    R("COC-P06", "CoC mismatch: conductivity vs flow",
      "off('cocmis')",
      "min(95, 30 + sev('cocmis'))",
      "Validate conductivity and flow meters; inspect overflow and leaks; hold any CoC increase.",
      ("coc",), priority="high", benefit="Reliable CoC and water-balance data"),
    R("COC-P07", "Opportunity to raise CoC",
      f"condvsp < -5 and {COC_CHEMISTRY_OK}",
      "min(95, 30 + min(40, -condvsp))",
      "Raise the conductivity setpoint gradually (0.25 to 0.5 CoC per step) and watch scale"
      " indicators.", ("coc",), priority="medium", benefit="Save water and chemicals"),
    R("COC-P08", "Corrosion / biological control risk",
      "low('orp') or low('ph') or low('lsi')",
      "min(95, 25 + sev('orp') + sev('ph') + sev('lsi'))",
      "Verify corrosion-inhibitor and biocide dosing; check the dosing pump and chemical tank.",
      ("coc",), priority="medium", benefit="Reduce corrosion · extend asset life"),
    R("COC-P09", "Chemical overdosing",
      "chemvt > 15 and not low('orp')",
      "min(95, 30 + min(40, chemvt - 15) + sev('orp'))",
      "Reduce the dose towards target and validate the ORP analyser.", ("coc",),
      priority="medium", benefit="Reduce chemical cost"),
    # --- Water balance (workbook Diagnostic Engine rule 2; Cause & Effect Matrix WB-01) ---
    R("WB-P01", "Unaccounted water / possible leak",
      "off('wberr')",
      "min(95, 35 + sev('wberr') + if_else(abs(wberr) > 15, 15, 0))",
      "Check basin overflow, drains, leaks and flowmeter calibration.", ("water_balance",),
      priority="high", benefit="Stop water loss · reliable water balance"),
    R("WB-P02", "Make-up differs from expected",
      "off('mudev')",
      "min(95, 30 + sev('mudev'))",
      "Investigate water loss, storage or the make-up meter; review blowdown.",
      ("water_balance",), priority="medium", benefit="Lower make-up water and chemical cost"),
]  # fmt: skip


FILTER_RULES = ["FLT-P01", "FLT-P02", "FLT-P03", "FLT-P04", "FLT-P05", "FLT-P06", "FLT-P07"]
THERMAL_RULES = ["TH-P01", "TH-P02", "TH-P03", "TH-P04", "TH-P05", "TH-P06"]
COC_RULES = [f"COC-P0{i}" for i in range(1, 10)]
# Water balance: its own rules plus the CoC rules about leaks and meter mismatch.
WATER_RULES = ["WB-P01", "WB-P02", "COC-P04", "COC-P06"]
# Trend charts: 6H / 24H / 7D / 30D buttons, four charts side by side.
TRENDS: dict[str, Any] = {"hours": 24, "ranges": [6, 24, 168, 720], "width": "quarter"}


def cards(keys: list[str]) -> list[dict[str, Any]]:
    """KPI cards whose targets are the plant's limits."""
    return [{"param": key, "target": "limits"} for key in keys]


MODULES = [
    TemplateModule(
        "water_chemistry",
        "Input Parameters",
        [
            {"type": "input_group", "title": "Chemistry", "group": "chemistry"},
            {"type": "input_group", "title": "Thermal", "group": "thermal"},
            {"type": "input_group", "title": "Side-stream filter", "group": "filter"},
            {"type": "input_group", "title": "Make-up, blowdown & dosing", "group": "coc"},
            {"type": "input_group", "title": "Water balance", "group": "water"},
            {
                "type": "input_group",
                "title": "Indication",
                "params": ["clean", "valve", "sspump", "bdvalve", "bwt"],
                "switches": ["clean", "valve", "sspump", "bdvalve"],
            },
            {
                "type": "value_tiles",
                "title": "Calculated values",
                "params": ["lsi", "range", "appr", "resid", "heat", "fan", "dp", "rem", "bw"],
                "only_calculated": True,
            },
        ],
    ),
    TemplateModule(
        "filter",
        "Side-Stream Filtration",
        [
            {"type": "kpi_cards", "title": "Filtration KPIs",
             "items": cards(["dp", "rem", "dprate", "solids"])},
            {"type": "kpi_cards", "title": "Cleaning",
             "items": cards(["cleancount", "cleanint", "dprec", "bw", "treated"])},
            {"type": "trend_chart", "title": "Filter ΔP", "params": ["dp"], **TRENDS},
            {"type": "trend_chart", "title": "Removal Efficiency", "params": ["rem"], **TRENDS},
            {"type": "trend_chart", "title": "Turbidity In & Out", "params": ["tin", "tout"],
             "combine": True, **TRENDS},
            {"type": "trend_chart", "title": "Side-Stream Flow", "params": ["ssflow"], **TRENDS},
            {"type": "predicted_problems", "title": "Predicted Problems", "rules": FILTER_RULES,
             "style": "table", "width": "half"},
            {"type": "recommended_actions", "title": "Recommended Actions", "rules": FILTER_RULES,
             "width": "half"},
            {
                "type": "inputs_summary",
                "title": "Inputs Used",
                "width": "half",
                "params": ["pin", "pout", "ssflow", "tin", "tout", "tssin", "tssout", "clean",
                           "bwf", "bwt", "oil", "valve", "sspump"],
            },
            {"type": "quick_links", "title": "Quick Actions", "width": "half", "items": [
                {"label": "Review filter readings", "target": "module:water_chemistry"},
                {"label": "Adjust filter limits", "target": "limits"},
                {"label": "Check thermal performance", "target": "module:thermal"},
                {"label": "Check CoC & blowdown", "target": "module:coc"},
            ]},
        ],
    ),
    TemplateModule(
        "thermal",
        "Thermal Efficiency",
        [
            {"type": "kpi_cards", "title": "Thermal KPIs",
             "items": cards(["appr", "expappr", "resid", "range", "heat", "fanresp", "sfe"])},
            {"type": "trend_chart", "title": "Approach & Residual", "params": ["appr", "resid"],
             "combine": True, **TRENDS},
            {"type": "trend_chart", "title": "Supply & Return Temperature", "params": ["ts", "tr"],
             "combine": True, **TRENDS},
            {"type": "trend_chart", "title": "Heat Load", "params": ["heat"], **TRENDS},
            {"type": "trend_chart", "title": "Fan Speed & Power", "params": ["fanspd", "fan"],
             "combine": True, **TRENDS},
            {"type": "predicted_problems", "title": "Predicted Problems", "rules": THERMAL_RULES,
             "style": "table", "width": "half"},
            {"type": "recommended_actions", "title": "Recommended Actions", "rules": THERMAL_RULES,
             "width": "half"},
            {
                "type": "inputs_summary",
                "title": "Inputs Used",
                "width": "half",
                "params": ["ts", "tr", "wbt", "flow", "fan", "fanspd", "pumpspd", "pumppow",
                           "pumpp", "load", "tin", "tssin"],
            },
            {"type": "quick_links", "title": "Quick Actions", "width": "half", "items": [
                {"label": "Review thermal readings", "target": "module:water_chemistry"},
                {"label": "Adjust thermal limits", "target": "limits"},
                {"label": "Check side-stream filter", "target": "module:filter"},
                {"label": "Check CoC & blowdown", "target": "module:coc"},
            ]},
        ],
    ),
    TemplateModule(
        "coc",
        "CoC & Blowdown",
        [
            {
                "type": "kpi_cards",
                "items": [
                    {"param": "coc", "target": "limits"},
                    {"param": "bdflow", "target": "limits"},
                    {"param": "cond", "target": "limits"},
                    {"param": "ph", "target": "limits"},
                    {"param": "orp", "target": "limits"},
                    {"param": "costsaved", "caption": "vs baseline", "delta": "mulower"},
                    {"param": "chemdose", "target": "limits", "caption": "vs target",
                     "delta": "chemvt", "delta_good": "down"},
                ],
            },
            {
                "type": "system_diagram",
                "title": "CoC & Blowdown System Overview",
                "width": "half",
                "makeup": "muflow",
                "blowdown": "bdflow",
                "sidestream": "dp",
                "chemistry": ["cond", "ph", "orp", "ts"],
            },
            {
                "type": "kpi_cards",
                "title": "Customer Benefits Today",
                "style": "benefit",
                "width": "half",
                "items": [
                    {"param": "bdlower", "caption": "vs baseline"},
                    {"param": "coc", "range_caption": True},
                    {"param": "orp", "range_caption": True},
                    {"param": "costsaved", "caption": "vs baseline"},
                    {"param": "mulower", "caption": "vs baseline"},
                ],
            },
            {"type": "trend_chart", "title": "CoC Trend", "params": ["coc"], **TRENDS},
            {"type": "trend_chart", "title": "Blowdown Trend", "params": ["bdflow", "bdreq"],
             "combine": True, **TRENDS},
            {"type": "trend_chart", "title": "Conductivity & pH", "params": ["cond", "ph"],
             "combine": True, **TRENDS},
            {"type": "trend_chart", "title": "ORP & Chemical Use", "params": ["orp", "chemdose"],
             "combine": True, **TRENDS},
            {"type": "predicted_problems", "title": "Predicted Problems", "rules": COC_RULES,
             "style": "table", "width": "third"},
            {"type": "recommended_actions", "title": "Recommended Actions", "rules": COC_RULES,
             "width": "third"},
            {
                "type": "quick_links",
                "title": "Quick Actions",
                "width": "third",
                "items": [
                    {"label": "Adjust blowdown setpoint", "target": "limits"},
                    {"label": "Review chemistry readings", "target": "module:water_chemistry"},
                    {"label": "Check side-stream filter", "target": "module:filter"},
                    {"label": "Check thermal performance", "target": "module:thermal"},
                ],
            },
        ],
    ),
    TemplateModule(
        "water_balance",
        "Water Balance",
        [
            {"type": "kpi_cards", "items": [
                {"param": "muflow", "target": "limits", "caption": "vs yesterday",
                 "delta": "muvsyday", "delta_good": "down"},
                {"param": "rwflow", "target": "limits", "caption": "vs yesterday",
                 "delta": "rwvsyday", "delta_good": "up"},
                {"param": "wberr", "target": "limits"},
                {"param": "bdflow", "target": "limits", "caption": "vs yesterday",
                 "delta": "bdvsyday", "delta_good": "down"},
                {"param": "evap", "target": "limits", "caption": "vs yesterday",
                 "delta": "evapvsyday", "delta_good": "down"},
                {"param": "watersaved", "caption": "vs baseline"},
            ]},
            {
                "type": "system_diagram",
                "title": "Water Balance Overview",
                "width": "half",
                "makeup": "muflow",
                "recycled": "rwflow",
                "evaporation": "evap",
                "blowdown": "bdflow",
                "chemistry": ["totalin", "explained", "unacc", "discharge", "storage"],
                "points_title": "Water flows",
            },
            {"type": "kpi_cards", "title": "Customer Benefits Today", "style": "benefit",
             "width": "half", "items": [
                {"param": "watersaved", "caption": "vs baseline"},
                {"param": "mulower", "caption": "less fresh water"},
                {"param": "recshare", "caption": "of water in is recycled"},
                {"param": "wbhealth", "range_caption": True},
                {"param": "excesscost", "caption": "avoidable today"},
            ]},
            {"type": "trend_chart", "title": "Make-up & Recycled", "params": ["muflow", "rwflow"],
             "combine": True, **TRENDS},
            {"type": "trend_chart", "title": "Evaporation & Blowdown", "params": ["evap", "bdflow"],
             "combine": True, **TRENDS},
            {"type": "trend_chart", "title": "Water Balance Error", "params": ["wberr"], **TRENDS},
            {"type": "trend_chart", "title": "Make-up vs Expected", "params": ["muflow", "expmu"],
             "combine": True, **TRENDS},
            {"type": "predicted_problems", "title": "Predicted Problems", "rules": WATER_RULES,
             "style": "table", "width": "third"},
            {"type": "recommended_actions", "title": "Recommended Actions", "rules": WATER_RULES,
             "width": "third"},
            {"type": "quick_links", "title": "Quick Actions", "width": "third", "items": [
                {"label": "Review water readings", "target": "module:water_chemistry"},
                {"label": "Adjust water limits", "target": "limits"},
                {"label": "Check CoC & blowdown", "target": "module:coc"},
                {"label": "Check side-stream filter", "target": "module:filter"},
            ]},
        ],
    ),
]  # fmt: skip


DEFAULT_TEMPLATE = Template(
    key="default",
    name="SMAYAA standard (Input Parameters, Side-Stream Filtration, Thermal Efficiency,"
    " CoC & Blowdown, Water Balance)",
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
        # CoC & Blowdown: target CoC (conductivity setpoint = make-up EC x target CoC), drift
        # (design estimate), baselines before optimisation, water cost and dosing target.
        "target_coc": 5.0,
        "drift_loss": 0.2,
        "baseline_blowdown": 4.7,
        "baseline_makeup": 21.5,
        "water_cost": 45.0,
        "chem_target": 2.6,
        # Water balance (workbook "Plant Inputs" design / target column): expected make-up uses
        # design blowdown, design other loss and design storage change; chemical cost per m³ of
        # make-up for the excess-cost estimate.
        "design_blowdown": 3.3,
        "design_other_loss": 0.3,
        "design_storage_change": 0.0,
        "chemical_cost": 18.0,
    },
)

TEMPLATES = {DEFAULT_TEMPLATE.key: DEFAULT_TEMPLATE}
