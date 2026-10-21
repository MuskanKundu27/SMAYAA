"""A small, safe evaluator for formulas and rule expressions.

Expressions are parsed with Python's `ast` module and then checked against a whitelist: only
numbers, names, arithmetic, comparisons, and/or/not, and calls to the functions listed below.
Anything else (attribute access, indexing, imports, lambdas, keyword arguments, ...) is
rejected before evaluation. We never call `eval`, `exec` or `compile` on user text.

Missing data is not an error: if a value is unknown (None), results that depend on it are None
("No data"). Division by zero, square roots of negatives, overflow etc. also give None.
"""

import ast
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

MAX_LENGTH = 500  # characters
MAX_NODES = 200  # parsed elements; keeps evaluation time tiny
MAX_EXPONENT = 100  # for **, so `9 ** 9 ** 9` cannot freeze the server

Value = float | bool | str | list[Any] | None


class ExpressionError(ValueError):
    """The expression is not allowed or not valid. The message is safe to show to users."""


_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
}
_COMPARE_OPS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.And,
    ast.Or,
    *_BIN_OPS,
    *_COMPARE_OPS,
)


def _num(*args: Value) -> bool:
    return all(isinstance(a, int | float) and not isinstance(a, bool) for a in args)


def _round(x: Value, digits: Value = 0) -> Value:
    if not _num(x, digits):
        return None
    return round(x, int(digits))  # type: ignore[arg-type]


def _sqrt(x: Value) -> Value:
    return math.sqrt(x) if _num(x) and x >= 0 else None  # type: ignore[operator,arg-type]


def _log(x: Value) -> Value:
    return math.log(x) if _num(x) and x > 0 else None  # type: ignore[operator,arg-type]


def _exp(x: Value) -> Value:
    if not _num(x):
        return None
    try:
        return math.exp(x)  # type: ignore[arg-type]
    except OverflowError:
        return None


def _min_max(fn: Callable[..., Any]) -> Callable[..., Value]:
    def wrapped(*args: Value) -> Value:
        if not args or not _num(*args):
            return None
        return float(fn(args))

    return wrapped


# Functions available in every expression. if_else is handled specially (lazily) below.
MATH_FUNCTIONS: dict[str, Callable[..., Value]] = {
    "min": _min_max(min),
    "max": _min_max(max),
    "abs": lambda x: abs(x) if _num(x) else None,
    "round": _round,
    "sqrt": _sqrt,
    "log": _log,
    "exp": _exp,
}
IF_ELSE = "if_else"

# Names that can never be parameter keys.
RESERVED_NAMES = frozenset(
    {*MATH_FUNCTIONS, IF_ELSE, "base", "value", "status", "off", "sev", "count_off"}
    | {"and", "or", "not", "true", "false", "none", "True", "False", "None"}
)


@dataclass(frozen=True)
class Expression:
    """A parsed and whitelisted expression, ready to evaluate many times."""

    source: str
    tree: ast.Expression
    # Every parameter key the expression depends on: bare names plus string arguments to
    # helpers like off('ph'). Used for validation and calculation order.
    references: frozenset[str] = field(default_factory=frozenset)


def parse(source: str, functions: Mapping[str, Callable[..., Value]] | None = None) -> Expression:
    """Parse and check an expression. `functions` are the extra helpers allowed (rules)."""
    allowed_functions = {*MATH_FUNCTIONS, IF_ELSE, *(functions or {})}
    if not source or not source.strip():
        raise ExpressionError("The expression is empty.")
    if len(source) > MAX_LENGTH:
        raise ExpressionError(f"The expression is longer than {MAX_LENGTH} characters.")
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Syntax error at position {exc.offset}: {exc.msg}.") from None

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise ExpressionError("The expression is too complex.")

    references: set[str] = set()
    function_names: set[int] = set()
    for node in nodes:
        if not isinstance(node, _ALLOWED_NODES):
            raise ExpressionError(f"'{type(node).__name__}' is not allowed in expressions.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in allowed_functions:
                name = node.func.id if isinstance(node.func, ast.Name) else "this call"
                raise ExpressionError(f"Unknown function '{name}'.")
            if node.keywords:
                raise ExpressionError("Keyword arguments are not allowed.")
            function_names.add(id(node.func))
            if node.func.id in (functions or {}):
                references.update(_string_args(node))
        elif isinstance(node, ast.Constant) and not isinstance(node.value, int | float | str):
            raise ExpressionError(f"The value {node.value!r} is not allowed.")
    for node in nodes:
        if isinstance(node, ast.Name) and id(node) not in function_names:
            if node.id in allowed_functions:
                raise ExpressionError(f"'{node.id}' is a function; call it like {node.id}(...).")
            references.add(node.id)
    return Expression(source=source.strip(), tree=tree, references=frozenset(references))


def _string_args(call: ast.Call) -> set[str]:
    keys: set[str] = set()
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            keys.add(arg.value)
        elif isinstance(arg, ast.List):
            keys.update(
                e.value
                for e in arg.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            )
    return keys


def evaluate(
    expression: Expression,
    variables: Mapping[str, float | None],
    functions: Mapping[str, Callable[..., Value]] | None = None,
) -> Value:
    """Evaluate a parsed expression. Never raises for data problems; returns None instead."""
    all_functions = {**MATH_FUNCTIONS, **(functions or {})}
    try:
        result = _eval(expression.tree.body, variables, all_functions)
    except (ArithmeticError, ValueError, TypeError):
        return None
    if isinstance(result, float) and not math.isfinite(result):
        return None
    return result


def _eval(
    node: ast.AST,
    variables: Mapping[str, float | None],
    functions: Mapping[str, Callable[..., Value]],
) -> Value:
    if isinstance(node, ast.Constant):
        return cast(Value, node.value)  # parse() only lets int, float and str through
    if isinstance(node, ast.Name):
        number = variables.get(node.id)
        return None if number is None else float(number)
    if isinstance(node, ast.List):
        return [_eval(e, variables, functions) for e in node.elts]
    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, variables, functions)
        if isinstance(node.op, ast.Not):
            return None if operand is None else not operand
        if not _num(operand):
            return None
        return -operand if isinstance(node.op, ast.USub) else operand  # type: ignore[operator]
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, variables, functions)
        right = _eval(node.right, variables, functions)
        if not _num(left, right):
            return None
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:  # type: ignore[arg-type]
            return None
        return _BIN_OPS[type(node.op)](left, right)  # type: ignore[arg-type]
    if isinstance(node, ast.BoolOp):
        # Short-circuit like Python; an unknown (None) operand makes the result unknown.
        is_and = isinstance(node.op, ast.And)
        for value_node in node.values:
            value = _eval(value_node, variables, functions)
            if value is None:
                return None
            if is_and and not value:
                return False
            if not is_and and value:
                return True
        return is_and
    if isinstance(node, ast.Compare):
        left = _eval(node.left, variables, functions)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval(comparator, variables, functions)
            if left is None or right is None:
                return None
            if not _COMPARE_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        name = node.func.id  # type: ignore[attr-defined]
        if name == IF_ELSE:
            # Lazy: only the chosen branch is evaluated, so if_else(x > 0, y / x, 0) is safe.
            if len(node.args) != 3:
                return None
            condition = _eval(node.args[0], variables, functions)
            if condition is None:
                return None
            return _eval(node.args[1] if condition else node.args[2], variables, functions)
        args = [_eval(a, variables, functions) for a in node.args]
        return functions[name](*args)
    raise ExpressionError(f"'{type(node).__name__}' is not allowed.")  # unreachable after parse
