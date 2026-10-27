"""Calculated parameters (dependency order, evaluation) and the helpers used by rules."""

from collections.abc import Callable, Iterable, Mapping

from app.engine.evaluator import Expression, Value, evaluate, parse
from app.engine.history import TIME_FUNCTIONS, History, TimeFunctions
from app.engine.status import NO_DATA, SEVERITY_POINTS, Limits, Status, status_of

BASE = "base"  # reserved formula name: the plant's clean baseline approach


def _no_data_helper(*_args: Value) -> Value:
    return None


# Plant helpers, available in formulas and rules:
#   setting('name')  a plant setting (design or threshold value), e.g. setting('design_flow')
#   known('key')     1 if the parameter has a value now, else 0 (for data-coverage scores)
PLANT_FUNCTIONS = ("setting", "known")

# parse() only needs the helper names; real helpers are bound to data at evaluation time.
_TIME_SIGNATURES: dict[str, Callable[..., Value]] = dict.fromkeys(
    (*TIME_FUNCTIONS, *PLANT_FUNCTIONS), _no_data_helper
)


def plant_functions(
    values: Mapping[str, float | None], settings: Mapping[str, float] | None
) -> dict[str, Callable[..., Value]]:
    def setting(name: Value) -> Value:
        value = (settings or {}).get(str(name))
        return float(value) if isinstance(value, int | float) else None

    def known(key: Value) -> Value:
        return 1.0 if values.get(str(key)) is not None else 0.0

    return {"setting": setting, "known": known}


def parse_formula(source: str) -> Expression:
    """Formulas may use the math functions and the time functions (engine/history.py)."""
    return parse(source, functions=_TIME_SIGNATURES)


def history_hours(expressions: Iterable[Expression]) -> float:
    """Hours of earlier readings needed to evaluate these expressions (0 = none)."""
    return max((e.history_hours for e in expressions), default=0.0)


class CycleError(ValueError):
    def __init__(self, keys: list[str]) -> None:
        super().__init__("Circular reference between: " + ", ".join(sorted(keys)))
        self.keys = sorted(keys)


def calculation_order(formulas: Mapping[str, Expression]) -> list[str]:
    """Order calculated keys so every formula runs after the formulas it uses (Kahn's algorithm).
    Raises CycleError if formulas depend on each other in a loop."""
    pending = {key: set(expr.references) & set(formulas) for key, expr in formulas.items()}
    order: list[str] = []
    while pending:
        ready = sorted(key for key, deps in pending.items() if not deps)
        if not ready:
            raise CycleError(list(pending))
        for key in ready:
            order.append(key)
            del pending[key]
        for deps in pending.values():
            deps.difference_update(ready)
    return order


def _as_number(result: Value) -> float | None:
    if isinstance(result, int | float) and not isinstance(result, bool):
        return float(result)
    return None


def calculate(
    inputs: Mapping[str, float | None],
    formulas: Mapping[str, Expression],
    base: float | None = None,
    history: History | None = None,
    settings: Mapping[str, float] | None = None,
) -> dict[str, float | None]:
    """Return the value of every calculated key. Unknown inputs give None, never an error.
    Without `history`, time functions (change, rate, ...) give None; without `settings`,
    setting('...') gives None."""
    values: dict[str, float | None] = {**inputs, BASE: base}
    time_functions = {
        **TimeFunctions(history, values).functions(),
        **plant_functions(values, settings),
    }
    results: dict[str, float | None] = {}
    for key in calculation_order(formulas):
        values[key] = results[key] = _as_number(evaluate(formulas[key], values, time_functions))
    return results


def statuses_for(
    values: Mapping[str, float | None], limits: Mapping[str, Limits | None]
) -> dict[str, Status]:
    return {key: status_of(values.get(key), limits.get(key)) for key in limits}


# --- Rule helpers ------------------------------------------------------------------------------

RULE_HELPERS = ("value", "status", "off", "high", "low", "sev", "count_off")


class RuleContext:
    """Read-only helpers available inside rule expressions:

    value('k')            the value of parameter k
    status('k')           'good', 'warn', 'bad' or 'na'
    off('k')              True when k is warn or bad
    high('k') / low('k')  True when k is off on the high / low side
    sev('k')              20 for warn, 40 for bad, else 0 (probability points)
    count_off(['a','b'])  how many of the listed parameters are off

    Missing data ('na') is not "off": no data must not raise a predicted problem.
    The time functions (change, rate, events, ...) are available too; see engine/history.py.
    """

    def __init__(
        self,
        values: Mapping[str, float | None],
        statuses: Mapping[str, Status],
        history: History | None = None,
        settings: Mapping[str, float] | None = None,
    ):
        self._values = values
        self._statuses = statuses
        self._time = TimeFunctions(history, values)
        self._plant = plant_functions(values, settings)

    @property
    def values(self) -> Mapping[str, float | None]:
        return self._values

    def _level(self, key: Value) -> str:
        return self._statuses.get(str(key), NO_DATA).level

    def _is_off(self, key: Value) -> bool:
        return self._level(key) in ("warn", "bad")

    def value(self, key: Value) -> Value:
        return self._values.get(str(key))

    def status(self, key: Value) -> Value:
        return self._level(key)

    def off(self, key: Value) -> Value:
        return self._is_off(key)

    def high(self, key: Value) -> Value:
        return self._is_off(key) and self._statuses[str(key)].direction == "high"

    def low(self, key: Value) -> Value:
        return self._is_off(key) and self._statuses[str(key)].direction == "low"

    def sev(self, key: Value) -> Value:
        level = self._level(key)
        return float(SEVERITY_POINTS[level]) if level in SEVERITY_POINTS else 0.0

    def count_off(self, keys: Value) -> Value:
        if not isinstance(keys, list):
            return None
        return float(sum(self._is_off(k) for k in keys))

    def functions(self) -> dict[str, Callable[..., Value]]:
        return {
            **self._time.functions(),
            **self._plant,
            **{name: getattr(self, name) for name in RULE_HELPERS},
        }


_RULE_SIGNATURES: dict[str, Callable[..., Value]] = {
    **_TIME_SIGNATURES,
    **dict.fromkeys(RULE_HELPERS, _no_data_helper),
}


def parse_rule(source: str) -> Expression:
    return parse(source, functions=_RULE_SIGNATURES)


def evaluate_rule(expression: Expression, context: RuleContext) -> Value:
    return evaluate(expression, context.values, context.functions())
