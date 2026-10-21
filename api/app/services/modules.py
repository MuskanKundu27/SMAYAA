"""Module layouts (lists of widgets) and treatments."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import Module, Parameter, Rule, Treatment
from app.schemas.config import (
    ModuleCreate,
    ModuleLayout,
    ModuleOut,
    ModuleUpdate,
    TreatmentIn,
    TreatmentOut,
)
from app.services import audit
from app.services.config_common import active_parameters, all_parameters, config_company

MODULE_FIELDS = ["key", "title", "sort_order", "is_active", "layout"]
TREATMENT_FIELDS = ["cause", "treatment", "precautions", "needs_review"]


def layout_warnings(db: Session, company_id: uuid.UUID, layout: dict[str, Any]) -> list[str]:
    """Widgets may reference missing/inactive items (they show "insufficient data"); list them."""
    params = set(active_parameters(db, company_id))
    rules = set(
        db.scalars(select(Rule.code).where(Rule.company_id == company_id, Rule.is_active.is_(True)))
    )
    warnings = []
    for i, widget in enumerate(layout.get("widgets", []), start=1):
        for key in widget.get("params") or []:
            if key not in params:
                warnings.append(f"Widget {i}: parameter '{key}' is missing or inactive.")
        for code in widget.get("rules") or []:
            if code not in rules:
                warnings.append(f"Widget {i}: rule '{code}' is missing or inactive.")
    return warnings


def to_out(db: Session, module: Module) -> ModuleOut:
    return ModuleOut(
        id=module.id, key=module.key, title=module.title, sort_order=module.sort_order,
        is_active=module.is_active, layout=module.layout,
        warnings=layout_warnings(db, module.company_id, module.layout),
    )  # fmt: skip


def _layout_json(layout: ModuleLayout) -> dict[str, Any]:
    return layout.model_dump(mode="json", exclude_none=True)


def list_modules(db: Session, principal: Principal, company_id: uuid.UUID) -> list[Module]:
    config_company(db, principal, company_id)
    return list(
        db.scalars(
            select(Module)
            .where(Module.company_id == company_id)
            .order_by(Module.sort_order, Module.key)
        )
    )


def create_module(
    db: Session, principal: Principal, company_id: uuid.UUID, data: ModuleCreate
) -> Module:
    config_company(db, principal, company_id)
    if db.scalar(select(Module.id).where(Module.company_id == company_id, Module.key == data.key)):
        raise ConflictError(f"A module with key '{data.key}' already exists.")
    module = Module(
        company_id=company_id, key=data.key, title=data.title, sort_order=data.sort_order,
        layout=_layout_json(data.layout),
    )  # fmt: skip
    db.add(module)
    db.flush()
    audit.record(
        db, principal, "module.create", "module", module.id,
        company_id=company_id, after=audit.snapshot(module, MODULE_FIELDS),
    )  # fmt: skip
    db.commit()
    return module


def update_module(
    db: Session, principal: Principal, company_id: uuid.UUID, key: str, data: ModuleUpdate
) -> Module:
    config_company(db, principal, company_id)
    module = db.scalar(select(Module).where(Module.company_id == company_id, Module.key == key))
    if module is None:
        raise NotFoundError(f"Module '{key}' not found.")
    before = audit.snapshot(module, MODULE_FIELDS)
    changes = data.model_dump(exclude_unset=True)
    for field in ("title", "sort_order", "is_active"):
        if field in changes:
            setattr(module, field, changes[field])
    if data.layout is not None:
        module.layout = _layout_json(data.layout)
    module.updated_at = datetime.now(UTC)
    audit.record(
        db, principal, "module.update", "module", module.id, company_id=company_id,
        before=before, after=audit.snapshot(module, MODULE_FIELDS),
    )  # fmt: skip
    db.commit()
    return module


# --- Treatments --------------------------------------------------------------------------------


def list_treatments(db: Session, principal: Principal, company_id: uuid.UUID) -> list[TreatmentOut]:
    config_company(db, principal, company_id)
    keys = {p.id: p.key for p in all_parameters(db, company_id)}
    treatments = db.scalars(select(Treatment).where(Treatment.company_id == company_id))
    return sorted(
        (
            TreatmentOut(
                id=t.id,
                parameter_key=keys.get(t.parameter_id, "?"),
                direction=t.direction,
                cause=t.cause,
                treatment=t.treatment,
                precautions=t.precautions,
                needs_review=t.needs_review,
            )
            for t in treatments
        ),
        key=lambda t: (t.parameter_key, t.direction),
    )


def upsert_treatments(
    db: Session, principal: Principal, company_id: uuid.UUID, items: list[TreatmentIn]
) -> list[TreatmentOut]:
    config_company(db, principal, company_id)
    params = {
        p.key: p for p in db.scalars(select(Parameter).where(Parameter.company_id == company_id))
    }
    unknown = sorted({i.parameter_key for i in items} - set(params))
    if unknown:
        raise ValidationFailedError(
            f"Unknown parameter(s): {', '.join(unknown)}.",
            [{"field": "parameter_key", "message": k} for k in unknown],
        )
    for item in items:
        parameter = params[item.parameter_key]
        treatment = db.scalar(
            select(Treatment).where(
                Treatment.parameter_id == parameter.id, Treatment.direction == item.direction
            )
        )
        before = audit.snapshot(treatment, TREATMENT_FIELDS) if treatment else None
        if treatment is None:
            treatment = Treatment(
                company_id=company_id, parameter_id=parameter.id, direction=item.direction
            )
            db.add(treatment)
        for field in TREATMENT_FIELDS:
            setattr(treatment, field, getattr(item, field))
        treatment.updated_at = datetime.now(UTC)
        db.flush()
        audit.record(
            db, principal, "treatment.upsert", "treatment", treatment.id,
            company_id=company_id, before=before, after=item.model_dump(),
        )  # fmt: skip
    db.commit()
    return list_treatments(db, principal, company_id)
