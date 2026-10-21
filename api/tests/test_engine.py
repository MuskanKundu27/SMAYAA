"""The calculation engine: safe evaluator, statuses, calculation order, rule helpers."""

import pytest

from app.engine.calculation import (
    CycleError,
    RuleContext,
    calculate,
    calculation_order,
    evaluate_rule,
    parse_rule,
    statuses_for,
)
from app.engine.evaluator import ExpressionError, evaluate, parse
from app.engine.status import Limits, Status, status_of


def run(source: str, **variables: float | None) -> object:
    return evaluate(parse(source), variables)


# --- Evaluating formulas ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("tr - ts", 8.0),
        ("1.163 * flow * (tr - ts)", 9304.0),
        ("(tin - tout) / tin * 100", pytest.approx(83.333, rel=1e-3)),
        ("-ts + 2 ** 3", -23.0),
        ("min(ts, tr, 35)", 31.0),
        ("max(ts, tr)", 39.0),
        ("abs(ts - tr)", 8.0),
        ("round(tr / 3, 1)", 13.0),
        ("sqrt(16)", 4.0),
        ("if_else(tr > ts, 1, 0)", 1),
        ("tr > ts and ts > 0", True),
        ("not (tr > ts)", False),
        ("20 < ts < 35", True),
    ],
)
def test_formulas_evaluate(source: str, expected: object) -> None:
    assert run(source, ts=31, tr=39, flow=1000, tin=12, tout=2) == expected


@pytest.mark.parametrize(
    "source",
    [
        "tr - ts",  # ts missing
        "a / 0",  # division by zero
        "sqrt(-1)",
        "log(0)",
        "exp(10000)",  # overflow
        "10 ** 1000",  # exponent above the cap
        "9 ** 9 ** 9",
        "min()",
    ],
)
def test_data_problems_give_none_instead_of_crashing(source: str) -> None:
    assert run(source, tr=39, a=1) is None


def test_if_else_only_evaluates_the_chosen_branch() -> None:
    assert run("if_else(x > 0, 10 / x, 0)", x=0) == 0
    assert run("if_else(x > 0, 10 / x, 0)", x=5) == 2.0


def test_unknown_condition_makes_if_else_unknown() -> None:
    assert run("if_else(x > 0, 1, 2)") is None


# --- Rejecting unsafe or invalid expressions ---------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "__import__('os').system('dir')",
        "ts.__class__",
        "open('x')",
        "eval('1')",
        "(lambda: 1)()",
        "[x for x in range(3)]",
        "ts[0]",
        "{'a': 1}",
        "max(ts, key=abs)",
        "ts if tr else 0",
        "f'{ts}'",
        "ts = 1",
        "x" * 501,
        "+".join(["1"] * 150),  # too many nodes
        "",
        "ts +",
        "min",  # function used as a value
    ],
)
def test_unsafe_or_invalid_expressions_are_rejected(source: str) -> None:
    with pytest.raises(ExpressionError):
        parse(source)


def test_references_list_every_name_used() -> None:
    assert parse("1.163 * flow * (tr - ts) + base").references == {"flow", "tr", "ts", "base"}


def test_rule_references_include_helper_string_arguments() -> None:
    expr = parse_rule("off('rem') or count_off(['tds', 'sio2']) > 0 and value('dp') > 1")
    assert expr.references == {"rem", "tds", "sio2", "dp"}


def test_rule_helpers_are_not_allowed_in_plain_formulas() -> None:
    with pytest.raises(ExpressionError, match="Unknown function 'off'"):
        parse("off('ph')")


# --- Status from limits ------------------------------------------------------------------------

PH = Limits(6.8, 7.2, 8.2, 8.8)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (7.9, Status("good")),
        (7.2, Status("good")),  # bounds are inclusive
        (8.5, Status("warn", "high")),
        (7.0, Status("warn", "low")),
        (9.0, Status("bad", "high")),
        (6.0, Status("bad", "low")),
        (None, Status("na")),
    ],
)
def test_status_of(value: float | None, expected: Status) -> None:
    assert status_of(value, PH) == expected


def test_no_limits_means_always_good() -> None:
    assert status_of(12345, None) == Status("good")


def test_limits_ordering() -> None:
    assert PH.is_ordered()
    assert not Limits(1, 3, 2, 4).is_ordered()


# --- Calculation order and full calculation ----------------------------------------------------


def test_formulas_run_after_the_formulas_they_use() -> None:
    formulas = {"resid": parse("appr - base"), "appr": parse("ts - wbt")}

    assert calculation_order(formulas) == ["appr", "resid"]
    assert calculate({"ts": 31, "wbt": 26}, formulas, base=4) == {"appr": 5.0, "resid": 1.0}


def test_circular_formulas_are_detected() -> None:
    formulas = {"a": parse("b + 1"), "b": parse("c + 1"), "c": parse("a + 1"), "d": parse("1")}

    with pytest.raises(CycleError) as exc:
        calculation_order(formulas)
    assert exc.value.keys == ["a", "b", "c"]


def test_missing_input_propagates_as_none() -> None:
    formulas = {"appr": parse("ts - wbt"), "resid": parse("appr - base")}

    assert calculate({"ts": 31}, formulas, base=4) == {"appr": None, "resid": None}


# --- Rule helpers ------------------------------------------------------------------------------


def make_context() -> RuleContext:
    limits = {"dp": Limits(0, 0, 0.8, 1.2), "rem": Limits(50, 70, 100, 100), "tds": None}
    values = {"dp": 1.0, "rem": 40.0, "tds": 1500.0}
    return RuleContext(values, statuses_for(values, limits))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("status('dp')", "warn"),
        ("status('rem')", "bad"),
        ("status('missing')", "na"),
        ("off('dp')", True),
        ("off('tds')", False),  # no limits: never off
        ("off('missing')", False),  # no data is not "off"
        ("sev('dp') + sev('rem')", 60.0),
        ("count_off(['dp', 'rem', 'tds', 'missing'])", 2.0),
        ("value('dp') > 0.8", True),
        ("min(95, 15 + 22 * count_off(['dp']) + sev('rem'))", 77.0),
    ],
)
def test_rule_helpers(source: str, expected: object) -> None:
    assert evaluate_rule(parse_rule(source), make_context()) == expected
