"""The current state of a plant: values, statuses, alerts and predicted problems.

Everything here is *derived* from input values plus the company's current configuration and the
plant's current limits (alerts are derived, not stored). The alert bar, module
screens and the live preview all use build_state(), so they always agree.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.calculation import RuleContext, calculate, evaluate_rule, parse_rule
from app.engine.evaluator import Expression, ExpressionError
from app.engine.status import Limits, Status, status_of
from app.models import Module, Parameter, Plant, Rule, Treatment
from app.schemas.config import LimitValues
from app.schemas.readings import Alert, PredictedProblem, Tile
from app.services.config_common import active_parameters, parsed_formulas
from app.services.limits import plant_limits, plant_setting

BASELINE_SETTING = "clean_baseline_approach"

FALLBACK_TREATMENT = {
    "cause": "No guidance has been configured for this parameter yet.",
    "treatment": "Re-check the measurement, then consult your water-treatment specialist.",
    "precautions": "Do not change chemical dosing without specialist advice.",
}


@dataclass
class PlantState:
    plant: Plant
    params: dict[str, Parameter]  # active parameters of the company
    limits: dict[str, Limits | None]  # effective limits per key
    values: dict[str, float | None]  # inputs + calculated (current formulas)
    statuses: dict[str, Status]
    base: float | None

    def tile(self, key: str, editable: bool = False) -> Tile:
        p = self.params.get(key)
        if p is None:
            return Tile(key=key, label=key, insufficient_data=True)
        status = self.statuses.get(key, Status("na"))
        limits = self.limits.get(key)
        return Tile(
            key=key,
            label=p.label,
            unit=p.unit,
            precision=p.precision,
            kind=p.kind,
            value=self.values.get(key),
            status=status.level,
            direction=status.direction,
            limits=LimitValues(**limits.__dict__) if limits else None,
            editable=editable and p.kind == "input",
        )


def _as_float(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def build_state(db: Session, plant: Plant, inputs: Mapping[str, object]) -> PlantState:
    params = active_parameters(db, plant.company_id)
    input_values = {
        key: _as_float(inputs.get(key)) for key, p in params.items() if p.kind == "input"
    }
    base = _as_float(plant_setting(db, plant, BASELINE_SETTING))
    values: dict[str, float | None] = {
        **input_values,
        **calculate(input_values, parsed_formulas(params.values()), base),
    }
    limits = {key: lim for key, (lim, _) in plant_limits(db, plant.id).items()}
    statuses = {key: status_of(values.get(key), limits.get(key)) for key in params}
    return PlantState(plant, params, limits, values, statuses, base)


# --- Which modules does a parameter affect? ----------------------------------------------------


def _rule_references(rule: Rule) -> set[str]:
    refs: set[str] = set()
    for source in (rule.condition_expr, rule.probability_expr):
        try:
            refs |= parse_rule(source).references
        except ExpressionError:
            continue
    return refs


def affected_modules(db: Session, state: PlantState) -> dict[str, list[str]]:
    """For each parameter key, the modules it affects, worked out from configuration:
    a module is affected if it shows the parameter (or a calculation that uses it), or shows
    a rule that uses it, or a rule using it names the module in affects_modules."""
    company_id = state.plant.company_id
    formulas = parsed_formulas(state.params.values())
    rules = list(
        db.scalars(select(Rule).where(Rule.company_id == company_id, Rule.is_active.is_(True)))
    )
    rule_refs = {r.code: _rule_references(r) for r in rules}
    modules = list(
        db.scalars(
            select(Module)
            .where(Module.company_id == company_id, Module.is_active.is_(True))
            .order_by(Module.sort_order, Module.key)
        )
    )

    # Keys that depend on each key, directly or through other calculations.
    users: defaultdict[str, set[str]] = defaultdict(set)
    for calc_key, expr in formulas.items():
        for ref in expr.references:
            users[ref].add(calc_key)

    def with_dependents(key: str) -> set[str]:
        seen, stack = {key}, [key]
        while stack:
            for dependent in users[stack.pop()] - seen:
                seen.add(dependent)
                stack.append(dependent)
        return seen

    module_keys: dict[str, set[str]] = {}  # module → parameter keys it uses
    for module in modules:
        keys: set[str] = set()
        for widget in module.layout.get("widgets", []):
            keys.update(widget.get("params") or [])
            group = widget.get("group")
            if widget.get("type") == "input_group" and group:
                keys.update(k for k, p in state.params.items() if p.group_key == group)
            for code in widget.get("rules") or []:
                keys.update(rule_refs.get(code, set()))
        module_keys[module.key] = keys
    for rule in rules:
        for module_key in rule.affects_modules:
            if module_key in module_keys:
                module_keys[module_key].update(rule_refs[rule.code])

    return {
        key: [m.key for m in modules if with_dependents(key) & module_keys[m.key]]
        for key in state.params
    }


# --- Alerts ------------------------------------------------------------------------------------


def alerts(db: Session, state: PlantState) -> list[Alert]:
    """Every parameter outside its good range, most severe first."""
    out_of_range = [
        key for key, status in state.statuses.items() if status.level in ("warn", "bad")
    ]
    if not out_of_range:
        return []
    treatments = {
        (t.parameter_id, t.direction): t
        for t in db.scalars(select(Treatment).where(Treatment.company_id == state.plant.company_id))
    }
    modules = affected_modules(db, state)
    result = []
    for key in out_of_range:
        p, status, limits = state.params[key], state.statuses[key], state.limits[key]
        value = state.values[key]
        if limits is None or value is None or status.direction is None:
            continue
        treatment = treatments.get((p.id, status.direction))
        texts = (
            {
                "cause": treatment.cause,
                "treatment": treatment.treatment,
                "precautions": treatment.precautions,
            }
            if treatment
            else FALLBACK_TREATMENT
        )
        result.append(
            Alert(
                parameter_key=key,
                label=p.label,
                unit=p.unit,
                value=value,
                level=status.level,
                severity="high" if status.level == "bad" else "medium",
                direction=status.direction,
                limits=LimitValues(**limits.__dict__),
                modules=modules.get(key, []),
                needs_review=treatment.needs_review if treatment else False,
                **texts,
            )
        )
    return sorted(result, key=lambda a: (a.severity != "high", a.label))


# --- Predicted problems ------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleResults:
    matched: list[PredictedProblem]  # sorted by probability, highest first
    insufficient: list[str]  # codes that could not be evaluated


def predicted_problems(db: Session, state: PlantState) -> RuleResults:
    """Evaluate every active rule. A rule whose inputs are missing or inactive is reported as
    insufficient data instead of guessing."""
    context = RuleContext(state.values, state.statuses)
    matched: list[PredictedProblem] = []
    insufficient: list[str] = []
    rules = db.scalars(
        select(Rule)
        .where(Rule.company_id == state.plant.company_id, Rule.is_active.is_(True))
        .order_by(Rule.sort_order, Rule.code)
    )
    for rule in rules:
        try:
            condition: Expression = parse_rule(rule.condition_expr)
            probability: Expression = parse_rule(rule.probability_expr)
        except ExpressionError:
            insufficient.append(rule.code)
            continue
        refs = condition.references | probability.references
        if any(state.values.get(k) is None for k in refs):
            insufficient.append(rule.code)
            continue
        if evaluate_rule(condition, context) is True:
            prob = _as_float(evaluate_rule(probability, context))
            matched.append(
                PredictedProblem(
                    code=rule.code,
                    title=rule.title,
                    probability=round(min(max(prob, 0.0), 100.0)) if prob is not None else None,
                    action=rule.action_text,
                    modules=list(rule.affects_modules),
                )
            )
    matched.sort(key=lambda p: -(p.probability or 0))
    return RuleResults(matched, insufficient)
