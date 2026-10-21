"""Calculated parameters (dependency order, evaluation) and the helpers used by rules."""

from collections.abc import Callable, Mapping

from app.engine.evaluator import Expression, Value, evaluate, parse
from app.engine.status import NO_DATA, SEVERITY_POINTS, Limits, Status, status_of

BASE = "base"  # reserved formula name: the plant's clean baseline approach


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
) -> dict[str, float | None]:
    """Return the value of every calculated key. Unknown inputs give None, never an error."""
    values: dict[str, float | None] = {**inputs, BASE: base}
    results: dict[str, float | None] = {}
    for key in calculation_order(formulas):
        values[key] = results[key] = _as_number(evaluate(formulas[key], values))
    return results


def statuses_for(
    values: Mapping[str, float | None], limits: Mapping[str, Limits | None]
) -> dict[str, Status]:
    return {key: status_of(values.get(key), limits.get(key)) for key in limits}


# --- Rule helpers ------------------------------------------------------------------------------

RULE_HELPERS = ("value", "status", "off", "sev", "count_off")


class RuleContext:
    """Read-only helpers available inside rule expressions:

    value('k')            the value of parameter k
    status('k')           'good', 'warn', 'bad' or 'na'
    off('k')              True when k is warn or bad
    sev('k')              20 for warn, 40 for bad, else 0 (probability points)
    count_off(['a','b'])  how many of the listed parameters are off

    Missing data ('na') is not "off": no data must not raise a predicted problem.
    """

    def __init__(self, values: Mapping[str, float | None], statuses: Mapping[str, Status]):
        self._values = values
        self._statuses = statuses

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

    def sev(self, key: Value) -> Value:
        level = self._level(key)
        return float(SEVERITY_POINTS[level]) if level in SEVERITY_POINTS else 0.0

    def count_off(self, keys: Value) -> Value:
        if not isinstance(keys, list):
            return None
        return float(sum(self._is_off(k) for k in keys))

    def functions(self) -> dict[str, Callable[..., Value]]:
        return {name: getattr(self, name) for name in RULE_HELPERS}


def _no_data_helper(*_args: Value) -> Value:
    return None


# parse() only needs the helper names; real helpers are bound to data at evaluation time.
_RULE_SIGNATURES: dict[str, Callable[..., Value]] = dict.fromkeys(RULE_HELPERS, _no_data_helper)


def parse_rule(source: str) -> Expression:
    return parse(source, functions=_RULE_SIGNATURES)


def evaluate_rule(expression: Expression, context: RuleContext) -> Value:
    return evaluate(expression, context.values, context.functions())
