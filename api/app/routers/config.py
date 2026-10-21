"""Company configuration (super admin, permission config.manage)."""

import uuid

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentPrincipal, DbSession
from app.schemas.config import (
    FormulaTest,
    FormulaTestResult,
    ModuleCreate,
    ModuleOut,
    ModuleUpdate,
    ParameterCreate,
    ParameterOut,
    ParameterUpdate,
    RuleCreate,
    RuleOut,
    RuleTest,
    RuleTestResult,
    RuleUpdate,
    TemplateApplied,
    TreatmentIn,
    TreatmentOut,
)
from app.services import modules, parameters, rules, templates

router = APIRouter(prefix="/companies/{company_id}", tags=["configuration (super admin)"])


# --- Parameters and formulas -------------------------------------------------------------------


@router.get("/parameters", response_model=list[ParameterOut])
def list_parameters(
    company_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ParameterOut]:
    return [parameters.to_out(p) for p in parameters.list_parameters(db, principal, company_id)]


@router.post("/parameters", response_model=ParameterOut, status_code=status.HTTP_201_CREATED)
def create_parameter(
    company_id: uuid.UUID, body: ParameterCreate, principal: CurrentPrincipal, db: DbSession
) -> ParameterOut:
    return parameters.to_out(parameters.create_parameter(db, principal, company_id, body))


@router.patch("/parameters/{key}", response_model=ParameterOut)
def update_parameter(
    company_id: uuid.UUID,
    key: str,
    body: ParameterUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> ParameterOut:
    """Deactivate with `{"is_active": false}`; refused (409) while formulas or rules use it."""
    return parameters.to_out(parameters.update_parameter(db, principal, company_id, key, body))


@router.post("/formulas/test", response_model=FormulaTestResult)
def test_formula(
    company_id: uuid.UUID, body: FormulaTest, principal: CurrentPrincipal, db: DbSession
) -> FormulaTestResult:
    """Try a formula on sample (or given) values. Nothing is saved."""
    return parameters.test_formula(db, principal, company_id, body)


# --- Treatments --------------------------------------------------------------------------------


@router.get("/treatments", response_model=list[TreatmentOut])
def list_treatments(
    company_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> list[TreatmentOut]:
    return modules.list_treatments(db, principal, company_id)


@router.put("/treatments", response_model=list[TreatmentOut])
def upsert_treatments(
    company_id: uuid.UUID, body: list[TreatmentIn], principal: CurrentPrincipal, db: DbSession
) -> list[TreatmentOut]:
    """Create or replace treatments, matched by parameter_key + direction."""
    return modules.upsert_treatments(db, principal, company_id, body)


# --- Rules -------------------------------------------------------------------------------------


@router.get("/rules", response_model=list[RuleOut])
def list_rules(company_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession) -> list[RuleOut]:
    return [RuleOut.model_validate(r) for r in rules.list_rules(db, principal, company_id)]


@router.post("/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    company_id: uuid.UUID, body: RuleCreate, principal: CurrentPrincipal, db: DbSession
) -> RuleOut:
    return RuleOut.model_validate(rules.create_rule(db, principal, company_id, body))


@router.patch("/rules/{code}", response_model=RuleOut)
def update_rule(
    company_id: uuid.UUID, code: str, body: RuleUpdate, principal: CurrentPrincipal, db: DbSession
) -> RuleOut:
    return RuleOut.model_validate(rules.update_rule(db, principal, company_id, code, body))


@router.post("/rules/test", response_model=RuleTestResult)
def test_rule(
    company_id: uuid.UUID, body: RuleTest, principal: CurrentPrincipal, db: DbSession
) -> RuleTestResult:
    """Try a rule on given input values (default limits). Nothing is saved."""
    return rules.test_rule(db, principal, company_id, body)


# --- Modules -----------------------------------------------------------------------------------


@router.get("/modules", response_model=list[ModuleOut])
def list_modules(
    company_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ModuleOut]:
    return [modules.to_out(db, m) for m in modules.list_modules(db, principal, company_id)]


@router.post("/modules", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(
    company_id: uuid.UUID, body: ModuleCreate, principal: CurrentPrincipal, db: DbSession
) -> ModuleOut:
    return modules.to_out(db, modules.create_module(db, principal, company_id, body))


@router.patch("/modules/{key}", response_model=ModuleOut)
def update_module(
    company_id: uuid.UUID,
    key: str,
    body: ModuleUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> ModuleOut:
    return modules.to_out(db, modules.update_module(db, principal, company_id, key, body))


# --- Templates ---------------------------------------------------------------------------------


@router.post("/apply-template", response_model=TemplateApplied)
def apply_template(
    company_id: uuid.UUID, principal: CurrentPrincipal, db: DbSession, template: str = "default"
) -> TemplateApplied:
    """Add whatever the template has and the company is missing. Existing items are kept."""
    return templates.apply_template_endpoint(db, principal, company_id, template)
