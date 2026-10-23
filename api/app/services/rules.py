"""Predicted-problem rules: validated like formulas, with the rule helpers available."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.engine.calculation import RuleContext, evaluate_rule, parse_rule
from app.engine.evaluator import Expression, ExpressionError
from app.models import Parameter, Rule
from app.schemas.config import RuleCreate, RuleTest, RuleTestResult, RuleUpdate
from app.services import audit
from app.services.config_common import (
    active_parameters,
    check_references,
    config_company,
    evaluate_with_defaults,
    expression_error,
    plant_setting_default,
    setting_defaults,
)

RULE_FIELDS = [
    "code", "title", "condition_expr", "probability_expr", "action_text", "affects_modules",
    "is_active", "version", "sort_order",
]  # fmt: skip


def _parse_checked(field: str, source: str, active: dict[str, Parameter]) -> Expression:
    try:
        expression = parse_rule(source)
    except ExpressionError as exc:
        raise expression_error(field, str(exc)) from None
    check_references(field, expression.references, active, allow_base=False)
    return expression


def list_rules(db: Session, principal: Principal, company_id: uuid.UUID) -> list[Rule]:
    config_company(db, principal, company_id)
    return list(
        db.scalars(
            select(Rule).where(Rule.company_id == company_id).order_by(Rule.sort_order, Rule.code)
        )
    )


def _get_rule(db: Session, company_id: uuid.UUID, code: str) -> Rule:
    rule = db.scalar(select(Rule).where(Rule.company_id == company_id, Rule.code == code))
    if rule is None:
        raise NotFoundError(f"Rule '{code}' not found.")
    return rule


def create_rule(db: Session, principal: Principal, company_id: uuid.UUID, data: RuleCreate) -> Rule:
    config_company(db, principal, company_id)
    if db.scalar(select(Rule.id).where(Rule.company_id == company_id, Rule.code == data.code)):
        raise ConflictError(f"A rule with code '{data.code}' already exists.")
    active = active_parameters(db, company_id)
    _parse_checked("condition_expr", data.condition_expr, active)
    _parse_checked("probability_expr", data.probability_expr, active)

    rule = Rule(company_id=company_id, **data.model_dump())
    db.add(rule)
    db.flush()
    audit.record(
        db, principal, "rule.create", "rule", rule.id,
        company_id=company_id, after=audit.snapshot(rule, RULE_FIELDS),
    )  # fmt: skip
    db.commit()
    return rule


def update_rule(
    db: Session, principal: Principal, company_id: uuid.UUID, code: str, data: RuleUpdate
) -> Rule:
    config_company(db, principal, company_id)
    rule = _get_rule(db, company_id, code)
    before = audit.snapshot(rule, RULE_FIELDS)
    changes: dict[str, Any] = data.model_dump(exclude_unset=True)

    expressions_changed = any(
        f in changes and changes[f] != getattr(rule, f)
        for f in ("condition_expr", "probability_expr")
    )
    if changes.get("is_active", rule.is_active) and (expressions_changed or not rule.is_active):
        active = active_parameters(db, company_id)
        _parse_checked("condition_expr", changes.get("condition_expr", rule.condition_expr), active)
        _parse_checked(
            "probability_expr", changes.get("probability_expr", rule.probability_expr), active
        )

    for field, value in changes.items():
        setattr(rule, field, value)
    if expressions_changed:
        rule.version += 1
    rule.updated_at = datetime.now(UTC)
    audit.record(
        db, principal, "rule.update", "rule", rule.id, company_id=company_id,
        before=before, after=audit.snapshot(rule, RULE_FIELDS),
    )  # fmt: skip
    db.commit()
    return rule


def test_rule(
    db: Session, principal: Principal, company_id: uuid.UUID, data: RuleTest
) -> RuleTestResult:
    """Evaluate a rule on given input values (using default limits) without saving."""
    company = config_company(db, principal, company_id)
    active = active_parameters(db, company_id)
    try:
        condition = _parse_checked("condition_expr", data.condition_expr, active)
        probability = (
            _parse_checked("probability_expr", data.probability_expr, active)
            if data.probability_expr
            else None
        )
    except ValidationFailedError as exc:
        return RuleTestResult(
            ok=False, matched=None, probability=None, references=[], error=exc.message
        )

    base = (
        data.base
        if data.base is not None
        else plant_setting_default(company, "clean_baseline_approach")
    )
    settings = setting_defaults(company)
    values, statuses = evaluate_with_defaults(active, data.values, base, settings)
    context = RuleContext(values, statuses, None, settings)
    matched = evaluate_rule(condition, context)
    prob = evaluate_rule(probability, context) if probability else None
    references = sorted(condition.references | (probability.references if probability else set()))
    return RuleTestResult(
        ok=matched is not None,
        matched=bool(matched) if matched is not None else None,
        probability=float(prob) if isinstance(prob, int | float) else None,
        references=references,
        error=None if matched is not None else "Not enough data to decide.",
    )
