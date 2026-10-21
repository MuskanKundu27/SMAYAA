"""Copy a template into a company.

Only adds what is missing (by parameter key, rule code, module key, treatment
parameter+direction), so applying twice is harmless and a company's own changes are kept.
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
from app.templates.default import TEMPLATES, Template


def apply_template(
    db: Session, company: Company, template: Template, actor_id: uuid.UUID | None
) -> dict[str, int]:
    """Add the template's missing items to the company. Does not commit."""
    cid = company.id
    params = {p.key: p for p in db.scalars(select(Parameter).where(Parameter.company_id == cid))}
    added = {"parameters": 0, "treatments": 0, "rules": 0, "modules": 0}

    for order, tp in enumerate(template.parameters):
        if tp.key in params:
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

    rule_codes = set(db.scalars(select(Rule.code).where(Rule.company_id == cid)))
    for order, tr in enumerate(template.rules):
        if tr.code in rule_codes:
            continue
        db.add(
            Rule(
                company_id=cid, code=tr.code, title=tr.title, condition_expr=tr.condition,
                probability_expr=tr.probability, action_text=tr.action,
                affects_modules=list(tr.affects), sort_order=order * 10,
            )
        )  # fmt: skip
        added["rules"] += 1

    module_keys = set(db.scalars(select(Module.key).where(Module.company_id == cid)))
    for order, tm in enumerate(template.modules):
        if tm.key in module_keys:
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
        after={"template": template.key, "added": added},
    )  # fmt: skip
    return added


def apply_template_endpoint(
    db: Session, principal: Principal, company_id: uuid.UUID, template_key: str
) -> TemplateApplied:
    company = config_company(db, principal, company_id)
    template = TEMPLATES.get(template_key)
    if template is None:
        raise NotFoundError(f"Template '{template_key}' not found.")
    added = apply_template(db, company, template, principal.user_id)
    db.commit()
    return TemplateApplied(template=template.key, added=added)
