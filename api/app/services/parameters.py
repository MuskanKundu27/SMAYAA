"""Parameters and formulas (CLAUDE brief §8).

On save a formula must: parse under the safe whitelist, reference only active parameters (or
`base`), not reference itself or create a loop, and give a result with sample values.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.engine.calculation import BASE, CycleError, calculate, calculation_order, parse_rule
from app.engine.evaluator import RESERVED_NAMES, ExpressionError, evaluate, parse
from app.models import Parameter, Rule
from app.schemas.config import (
    FormulaTest,
    FormulaTestResult,
    LimitValues,
    ParameterCreate,
    ParameterOut,
    ParameterUpdate,
)
from app.services import audit
from app.services.config_common import (
    active_parameters,
    all_parameters,
    check_references,
    config_company,
    default_limits,
    expression_error,
    parsed_formulas,
    plant_setting_default,
    sample_inputs,
)

PARAMETER_FIELDS = [
    "key", "label", "unit", "group_key", "kind", "formula", "formula_version", "precision",
    "sort_order", "is_active", "sample_value", "default_warn_min", "default_good_min",
    "default_good_max", "default_warn_max",
]  # fmt: skip


def to_out(p: Parameter) -> ParameterOut:
    limits = default_limits(p)
    return ParameterOut(
        id=p.id, key=p.key, label=p.label, unit=p.unit, group_key=p.group_key, kind=p.kind,
        formula=p.formula, formula_version=p.formula_version, precision=p.precision,
        sort_order=p.sort_order, is_active=p.is_active, sample_value=p.sample_value,
        default_limits=LimitValues(**limits.__dict__) if limits else None,
        updated_at=p.updated_at,
    )  # fmt: skip


def validate_formula(
    key: str, formula: str, active: dict[str, Parameter], base: float | None
) -> None:
    """Raise ValidationFailedError (field 'formula') unless the formula is safe and usable."""
    try:
        expression = parse(formula)
    except ExpressionError as exc:
        raise expression_error("formula", str(exc)) from None
    if key in expression.references:
        raise expression_error("formula", "A formula cannot use its own parameter.")
    check_references("formula", expression.references, (k for k in active if k != key))

    others = {k: p for k, p in active.items() if k != key}
    formulas = {**parsed_formulas(others.values()), key: expression}
    try:
        calculation_order(formulas)
    except CycleError as exc:
        raise expression_error("formula", str(exc)) from None

    results = calculate(sample_inputs(others), formulas, base)
    if results.get(key) is None:
        raise expression_error(
            "formula",
            "The formula gives no result with the sample values (division by zero, or an "
            "input without a value?).",
        )


def dependents_of(db: Session, company_id: uuid.UUID, key: str) -> list[str]:
    """Active formulas and rules that use this parameter."""
    users = [
        f"parameter '{k}'"
        for k, expr in parsed_formulas(active_parameters(db, company_id).values()).items()
        if key in expr.references
    ]
    rules = db.scalars(select(Rule).where(Rule.company_id == company_id, Rule.is_active.is_(True)))
    for rule in rules:
        refs: set[str] = set()
        for source in (rule.condition_expr, rule.probability_expr):
            try:
                refs |= parse_rule(source).references
            except ExpressionError:
                continue
        if key in refs:
            users.append(f"rule '{rule.code}'")
    return sorted(users)


def _set_default_limits(p: Parameter, limits: LimitValues | None) -> None:
    p.default_warn_min = limits.warn_min if limits else None
    p.default_good_min = limits.good_min if limits else None
    p.default_good_max = limits.good_max if limits else None
    p.default_warn_max = limits.warn_max if limits else None


def list_parameters(db: Session, principal: Principal, company_id: uuid.UUID) -> list[Parameter]:
    config_company(db, principal, company_id)
    return all_parameters(db, company_id)


def get_parameter(db: Session, company_id: uuid.UUID, key: str) -> Parameter:
    p = db.scalar(select(Parameter).where(Parameter.company_id == company_id, Parameter.key == key))
    if p is None:
        raise NotFoundError(f"Parameter '{key}' not found.")
    return p


def create_parameter(
    db: Session, principal: Principal, company_id: uuid.UUID, data: ParameterCreate
) -> Parameter:
    company = config_company(db, principal, company_id)
    if data.key in RESERVED_NAMES:
        raise expression_error("key", f"'{data.key}' is a reserved name.")
    exists = db.scalar(
        select(Parameter.id).where(Parameter.company_id == company_id, Parameter.key == data.key)
    )
    if exists:
        raise ConflictError(f"A parameter with key '{data.key}' already exists.")
    if data.kind == "calculated":
        if not data.formula:
            raise expression_error("formula", "A calculated parameter needs a formula.")
        validate_formula(
            data.key, data.formula, active_parameters(db, company_id),
            plant_setting_default(company, "clean_baseline_approach"),
        )  # fmt: skip
    elif data.formula:
        raise expression_error("formula", "Typed-in parameters do not have a formula.")

    p = Parameter(
        company_id=company_id, key=data.key, label=data.label, unit=data.unit,
        group_key=data.group_key, kind=data.kind,
        formula=data.formula if data.kind == "calculated" else None,
        formula_version=1 if data.kind == "calculated" else 0,
        precision=data.precision, sort_order=data.sort_order, sample_value=data.sample_value,
    )  # fmt: skip
    _set_default_limits(p, data.default_limits)
    db.add(p)
    db.flush()
    audit.record(
        db, principal, "parameter.create", "parameter", p.id,
        company_id=company_id, after=audit.snapshot(p, PARAMETER_FIELDS),
    )  # fmt: skip
    db.commit()
    return p


def update_parameter(
    db: Session, principal: Principal, company_id: uuid.UUID, key: str, data: ParameterUpdate
) -> Parameter:
    company = config_company(db, principal, company_id)
    p = get_parameter(db, company_id, key)
    before = audit.snapshot(p, PARAMETER_FIELDS)
    changes: dict[str, Any] = data.model_dump(exclude_unset=True)

    if changes.get("is_active") is False and p.is_active:
        users = dependents_of(db, company_id, key)
        if users:
            raise ConflictError(
                f"'{key}' is still used by: {', '.join(users)}. Change those first.",
                [{"field": "is_active", "message": u} for u in users],
            )

    new_formula = changes.get("formula", p.formula)
    if "formula" in changes and p.kind == "input" and new_formula:
        raise expression_error("formula", "Typed-in parameters do not have a formula.")
    becomes_active = changes.get("is_active", p.is_active)
    formula_changed = "formula" in changes and new_formula != p.formula
    if p.kind == "calculated" and becomes_active and (formula_changed or not p.is_active):
        if not new_formula:
            raise expression_error("formula", "A calculated parameter needs a formula.")
        validate_formula(
            key, new_formula, active_parameters(db, company_id),
            plant_setting_default(company, "clean_baseline_approach"),
        )  # fmt: skip

    for field in ("label", "unit", "group_key", "precision", "sort_order", "sample_value"):
        if field in changes:
            setattr(p, field, changes[field])
    if "default_limits" in changes:
        _set_default_limits(p, data.default_limits)
    if "is_active" in changes:
        p.is_active = changes["is_active"]
    if formula_changed:
        p.formula = new_formula
        p.formula_version += 1  # old readings keep the version they were calculated with
    p.updated_at = datetime.now(UTC)

    audit.record(
        db, principal, "parameter.update", "parameter", p.id, company_id=company_id,
        before=before, after=audit.snapshot(p, PARAMETER_FIELDS),
    )  # fmt: skip
    db.commit()
    return p


def test_formula(
    db: Session, principal: Principal, company_id: uuid.UUID, data: FormulaTest
) -> FormulaTestResult:
    """Evaluate a formula on sample or given values without saving anything."""
    company = config_company(db, principal, company_id)
    active = active_parameters(db, company_id)
    try:
        expression = parse(data.formula)
        check_references("formula", expression.references, active)
    except ExpressionError as exc:
        return FormulaTestResult(ok=False, result=None, references=[], error=str(exc))
    except ValidationFailedError as exc:
        return FormulaTestResult(
            ok=False, result=None, references=sorted(expression.references), error=exc.message
        )

    inputs = sample_inputs(active) if data.values is None else dict(data.values)
    base = (
        data.base
        if data.base is not None
        else plant_setting_default(company, "clean_baseline_approach")
    )
    values: dict[str, float | None] = {**inputs, BASE: base}
    values.update(calculate(inputs, parsed_formulas(active.values()), base))
    result = evaluate(expression, values)
    if isinstance(result, str | list):
        result = None
    return FormulaTestResult(
        ok=result is not None, result=result, references=sorted(expression.references),
        error=None if result is not None else "No result with these values.",
    )  # fmt: skip
