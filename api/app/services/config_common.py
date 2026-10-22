"""Helpers shared by the configuration services."""

import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import NotFoundError, ValidationFailedError
from app.engine.calculation import BASE, calculate, parse_formula, statuses_for
from app.engine.evaluator import Expression, ExpressionError
from app.engine.status import Limits, Status
from app.models import Company, Parameter

SAMPLE_FALLBACK = 1.0  # used for inputs without a sample value when testing formulas
PLANT_SETTING_DEFAULTS_KEY = "plant_setting_defaults"  # in companies.settings


def config_company(db: Session, principal: Principal, company_id: uuid.UUID) -> Company:
    """The company whose configuration the super admin is working on."""
    principal.require("config.manage")
    company = db.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company not found.")
    return company


def all_parameters(db: Session, company_id: uuid.UUID) -> list[Parameter]:
    return list(
        db.scalars(
            select(Parameter)
            .where(Parameter.company_id == company_id)
            .order_by(Parameter.group_key, Parameter.sort_order, Parameter.key)
        )
    )


def active_parameters(db: Session, company_id: uuid.UUID) -> dict[str, Parameter]:
    return {p.key: p for p in all_parameters(db, company_id) if p.is_active}


def parsed_formulas(parameters: Iterable[Parameter]) -> dict[str, Expression]:
    formulas = {}
    for p in parameters:
        if p.kind == "calculated" and p.formula:
            try:
                formulas[p.key] = parse_formula(p.formula)
            except ExpressionError:
                continue  # validated on save; a bad stored formula just yields no value
    return formulas


def default_limits(parameter: Parameter) -> Limits | None:
    if parameter.default_warn_min is None:
        return None
    return Limits(
        parameter.default_warn_min,
        parameter.default_good_min,  # type: ignore[arg-type]
        parameter.default_good_max,  # type: ignore[arg-type]
        parameter.default_warn_max,  # type: ignore[arg-type]
    )


def sample_inputs(parameters: Mapping[str, Parameter]) -> dict[str, float | None]:
    return {
        key: p.sample_value if p.sample_value is not None else SAMPLE_FALLBACK
        for key, p in parameters.items()
        if p.kind == "input"
    }


def plant_setting_default(company: Company, key: str) -> Any:
    return (company.settings or {}).get(PLANT_SETTING_DEFAULTS_KEY, {}).get(key)


def evaluate_with_defaults(
    parameters: Mapping[str, Parameter],
    inputs: Mapping[str, float | None],
    base: float | None,
) -> tuple[dict[str, float | None], dict[str, Status]]:
    """All values (inputs + calculated) and their statuses using default limits."""
    values: dict[str, float | None] = {
        k: v for k, v in inputs.items() if k in parameters and parameters[k].kind == "input"
    }
    values.update(calculate(values, parsed_formulas(parameters.values()), base))
    limits = {key: default_limits(p) for key, p in parameters.items()}
    return values, statuses_for(values, limits)


def expression_error(field: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(message, [{"field": field, "message": message}])


def check_references(
    field: str, references: Iterable[str], known: Iterable[str], allow_base: bool = True
) -> None:
    allowed = set(known) | ({BASE} if allow_base else set())
    unknown = sorted(set(references) - allowed)
    if unknown:
        raise expression_error(field, f"Unknown or inactive parameter(s): {', '.join(unknown)}.")
