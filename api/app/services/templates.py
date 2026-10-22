"""Copy a template into a company.

Normally only adds what is missing (by parameter key, rule code, module key, treatment
parameter+direction), so applying twice is harmless and a company's own changes are kept.

`update_existing=True` is the explicit "update to the latest template" action: the template's
own parameters, rules and modules are also brought up to date (formulas, conditions, layouts),
overwriting edits to those items. Items the company added itself and treatments are never
touched. Formula and rule versions go up, so stored readings keep their history.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import NotFoundError
from app.models import Company, Module, Parameter, Rule, Treatment
from app.schemas.config import TemplateApplied
from app.services import audit
from app.services.config_common import PLANT_SETTING_DEFAULTS_KEY, config_company
from app.templates.default import TEMPLATES, Template, TemplateParameter, TemplateRule


def _limits_of(p: Parameter) -> tuple[float | None, ...]:
    return (p.default_warn_min, p.default_good_min, p.default_good_max, p.default_warn_max)


def _update_parameter(p: Parameter, tp: TemplateParameter) -> bool:
    before = (p.label, p.unit, p.group_key, p.formula, p.precision, _limits_of(p))
    if p.kind == "calculated" and tp.formula is not None and p.formula != tp.formula:
        p.formula = tp.formula
        p.formula_version += 1
    p.label, p.unit, p.group_key, p.precision = tp.label, tp.unit, tp.group, tp.precision
    (p.default_warn_min, p.default_good_min, p.default_good_max, p.default_warn_max) = (
        tp.limits or (None, None, None, None)
    )
    return before != (p.label, p.unit, p.group_key, p.formula, p.precision, _limits_of(p))


def _update_rule(rule: Rule, tr: TemplateRule) -> bool:
    before = (rule.title, rule.condition_expr, rule.probability_expr, rule.action_text,
              list(rule.affects_modules))  # fmt: skip
    if (rule.condition_expr, rule.probability_expr) != (tr.condition, tr.probability):
        rule.version += 1
    rule.title, rule.condition_expr, rule.probability_expr = tr.title, tr.condition, tr.probability
    rule.action_text, rule.affects_modules = tr.action, list(tr.affects)
    after = (rule.title, rule.condition_expr, rule.probability_expr, rule.action_text,
             list(rule.affects_modules))  # fmt: skip
    return before != after


def apply_template(
    db: Session,
    company: Company,
    template: Template,
    actor_id: uuid.UUID | None,
    update_existing: bool = False,
) -> tuple[dict[str, int], dict[str, int]]:
    """Add the template's missing items to the company (and, with update_existing, refresh
    the template's existing items). Does not commit. Returns (added, updated) counts."""
    cid = company.id
    params = {p.key: p for p in db.scalars(select(Parameter).where(Parameter.company_id == cid))}
    added = {"parameters": 0, "treatments": 0, "rules": 0, "modules": 0}
    updated = {"parameters": 0, "rules": 0, "modules": 0}

    for order, tp in enumerate(template.parameters):
        if tp.key in params:
            if update_existing and _update_parameter(params[tp.key], tp):
                updated["parameters"] += 1
            continue
        p = Parameter(
            company_id=cid, key=tp.key, label=tp.label, unit=tp.unit, group_key=tp.group,
            kind="calculated" if tp.formula else "input", formula=tp.formula,
            formula_version=1 if tp.formula else 0, precision=tp.precision,
            sort_order=order * 10, sample_value=tp.sample,
        )  # fmt: skip
        if tp.limits:
            (p.default_warn_min, p.default_good_min, p.default_good_max, p.default_warn_max) = (
                tp.limits
            )
        db.add(p)
        params[tp.key] = p
        added["parameters"] += 1
    db.flush()

    existing_treatments = set(
        db.execute(
            select(Treatment.parameter_id, Treatment.direction).where(Treatment.company_id == cid)
        ).tuples()
    )
    for tt in template.treatments:
        param = params.get(tt.key)
        if param is None or (param.id, tt.direction) in existing_treatments:
            continue
        db.add(
            Treatment(
                company_id=cid, parameter_id=param.id, direction=tt.direction, cause=tt.cause,
                treatment=tt.treatment, precautions=tt.precautions, needs_review=True,
            )
        )  # fmt: skip
        added["treatments"] += 1

    rules = {r.code: r for r in db.scalars(select(Rule).where(Rule.company_id == cid))}
    for order, tr in enumerate(template.rules):
        if tr.code in rules:
            if update_existing and _update_rule(rules[tr.code], tr):
                updated["rules"] += 1
            continue
        db.add(
            Rule(
                company_id=cid, code=tr.code, title=tr.title, condition_expr=tr.condition,
                probability_expr=tr.probability, action_text=tr.action,
                affects_modules=list(tr.affects), sort_order=order * 10,
            )
        )  # fmt: skip
        added["rules"] += 1

    modules = {m.key: m for m in db.scalars(select(Module).where(Module.company_id == cid))}
    for order, tm in enumerate(template.modules):
        if tm.key in modules:
            module, layout = modules[tm.key], {"widgets": tm.widgets}
            if update_existing and (module.title, module.layout) != (tm.title, layout):
                module.title, module.layout = tm.title, layout
                updated["modules"] += 1
            continue
        db.add(
            Module(
                company_id=cid, key=tm.key, title=tm.title, sort_order=order * 10,
                layout={"widgets": tm.widgets},
            )
        )  # fmt: skip
        added["modules"] += 1

    settings: dict[str, Any] = dict(company.settings or {})
    defaults = dict(settings.get(PLANT_SETTING_DEFAULTS_KEY, {}))
    for key, value in template.plant_setting_defaults.items():
        defaults.setdefault(key, value)
    settings[PLANT_SETTING_DEFAULTS_KEY] = defaults
    company.settings = settings  # reassign so SQLAlchemy notices the JSONB change

    db.flush()
    audit.record_for(
        db, actor_id, "template.apply", "company", cid, company_id=cid,
        after={"template": template.key, "added": added,
               "updated": updated if update_existing else None},
    )  # fmt: skip
    return added, updated


def apply_template_endpoint(
    db: Session,
    principal: Principal,
    company_id: uuid.UUID,
    template_key: str,
    update_existing: bool = False,
) -> TemplateApplied:
    company = config_company(db, principal, company_id)
    template = TEMPLATES.get(template_key)
    if template is None:
        raise NotFoundError(f"Template '{template_key}' not found.")
    added, updated = apply_template(db, company, template, principal.user_id, update_existing)
    db.commit()
    return TemplateApplied(
        template=template.key, added=added, updated=updated if update_existing else {}
    )
