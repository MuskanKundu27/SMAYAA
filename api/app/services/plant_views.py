"""Module screens and the alert bar for plant users.

GET /plants/{id}/modules/{key} returns the module's widget layout with the data each widget
needs, so the frontend only draws (it never calculates or decides statuses itself).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.core.errors import NotFoundError, ValidationFailedError
from app.models import Module, Plant, Reading
from app.schemas.config import LimitValues, QuickLink
from app.schemas.readings import (
    Alert,
    KpiCard,
    ModuleSummary,
    ModuleView,
    PlantAlerts,
    TrendPoint,
    TrendSeries,
    WidgetView,
)
from app.services.plant_state import (
    PlantState,
    RuleResults,
    alerts,
    build_state,
    predicted_problems,
)
from app.services.plants import get_plant_in_scope
from app.services.readings import can_edit_readings, latest_reading, operator_profile, summary

TREND_MAX_POINTS = 500


def _visible_modules(
    db: Session, principal: Principal, plant_id: uuid.UUID, company_id: uuid.UUID
) -> list[Module]:
    modules = list(
        db.scalars(
            select(Module)
            .where(Module.company_id == company_id, Module.is_active.is_(True))
            .order_by(Module.sort_order, Module.key)
        )
    )
    profile = operator_profile(db, principal, plant_id)
    if profile is not None and profile.visible_modules is not None:
        allowed = set(profile.visible_modules)
        modules = [m for m in modules if m.key in allowed]
    return modules


def list_modules(db: Session, principal: Principal, plant_id: uuid.UUID) -> list[ModuleSummary]:
    principal.require("modules.view")
    plant = get_plant_in_scope(db, principal, plant_id)
    return [
        ModuleSummary(key=m.key, title=m.title, sort_order=m.sort_order)
        for m in _visible_modules(db, principal, plant.id, plant.company_id)
    ]


def _trend(db: Session, state: PlantState, keys: list[str], hours: int) -> list[TrendSeries]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = db.scalars(
        select(Reading)
        .where(Reading.plant_id == state.plant.id, Reading.recorded_at >= since)
        .order_by(Reading.recorded_at.desc())
        .limit(TREND_MAX_POINTS)
    ).all()
    series = []
    for key in keys:
        p = state.params.get(key)
        if p is None:
            continue
        limits = state.limits.get(key)
        points = [
            TrendPoint(t=r.recorded_at, v=(r.input_values | r.calculated_values).get(key))
            for r in reversed(rows)
        ]
        series.append(
            TrendSeries(
                key=key,
                label=p.label,
                unit=p.unit,
                points=points,
                limits=LimitValues(**limits.__dict__) if limits else None,
            )
        )
    return series


def _widget_view(
    db: Session,
    widget: dict[str, Any],
    state: PlantState,
    editable: bool,
    rule_results: RuleResults,
    plant_alerts: list[Alert],
) -> WidgetView:
    view = _widget_content(db, widget, state, editable, rule_results, plant_alerts)
    view.width = widget.get("width", "full")
    return view


def _widget_content(
    db: Session,
    widget: dict[str, Any],
    state: PlantState,
    editable: bool,
    rule_results: RuleResults,
    plant_alerts: list[Alert],
) -> WidgetView:
    kind = widget.get("type", "")
    title = widget.get("title", "")
    params: list[str] = widget.get("params") or []

    if kind == "input_group":
        group = widget.get("group")
        keys = params or [
            k for k, p in state.params.items() if p.group_key == group and p.kind == "input"
        ]
        return WidgetView(
            type=kind,
            title=title,
            tiles=[state.tile(k, editable) for k in keys],
            switches=widget.get("switches") or None,
        )
    if kind in ("value_tiles", "inputs_summary"):
        if widget.get("only_calculated"):
            params = [k for k in params if k not in state.params or state.params[k].kind != "input"]
        return WidgetView(type=kind, title=title, tiles=[state.tile(k) for k in params])
    if kind == "predicted_problems":
        codes = set(widget.get("rules") or [])
        return WidgetView(
            type=kind,
            title=title,
            style=widget.get("style", "list"),
            problems=[p for p in rule_results.matched if p.code in codes],
            insufficient_rules=sorted(codes & set(rule_results.insufficient)),
        )
    if kind == "recommended_actions":
        codes = set(widget.get("rules") or [])
        return WidgetView(
            type=kind, title=title, problems=[p for p in rule_results.matched if p.code in codes]
        )
    if kind == "kpi_cards":
        return WidgetView(
            type=kind,
            title=title,
            style=widget.get("style", "kpi"),
            cards=[_kpi_card(item, state) for item in widget.get("items") or []],
        )
    if kind == "quick_links":
        return WidgetView(
            type=kind, title=title, links=[QuickLink(**i) for i in widget.get("items") or []]
        )
    if kind == "system_diagram":
        roles = ("makeup", "blowdown", "sidestream")
        return WidgetView(
            type=kind,
            title=title,
            named={role: state.tile(widget[role]) for role in roles if widget.get(role)},
            tiles=[state.tile(k) for k in widget.get("chemistry") or []],
        )
    if kind == "alert_list":
        only_modules = set(widget.get("modules") or [])
        only_keys = set(params)
        shown = [
            a
            for a in plant_alerts
            if (not only_modules or only_modules & set(a.modules))
            and (not only_keys or a.parameter_key in only_keys)
        ]
        return WidgetView(type=kind, title=title, alerts=shown)
    if kind == "trend_chart":
        hours = int(widget.get("hours", 24))
        return WidgetView(
            type=kind,
            title=title,
            series=_trend(db, state, params, hours),
            hours=hours,
            ranges=widget.get("ranges") or None,
            combine=bool(widget.get("combine", False)),
        )
    if kind == "text_note":
        return WidgetView(type=kind, title=title, text=widget.get("text", ""))
    return WidgetView(type=kind, title=title)  # unknown type: the frontend shows a placeholder


def _kpi_card(item: dict[str, Any], state: PlantState) -> KpiCard:
    """One KPI or benefit card: the value, a target (the good range, or another parameter's
    value as an upper target), the status colour and an optional % change."""
    key = item["param"]
    tile = state.tile(key)
    target = item.get("target")
    target_min = target_max = None
    if target == "limits" and tile.limits is not None:
        target_min, target_max = tile.limits.good_min, tile.limits.good_max
    elif target and target != "limits":
        target_max = state.values.get(target)
    status_key = item.get("status_from") or key
    status = state.statuses.get(status_key)
    # Without limits there is no target, so no status colour either ("good" would mislead).
    has_limits = state.limits.get(status_key) is not None
    level = status.level if status and status_key in state.params and has_limits else "na"
    delta_key = item.get("delta")
    caption = item.get("caption", "")
    if target == "limits" and tile.limits is None and not caption and tile.value is not None:
        caption = "No target set"  # the manager sets the plant's range on the Limits page
    return KpiCard(
        tile=tile,
        caption=caption,
        target_min=target_min,
        target_max=target_max,
        status=level,
        delta=state.values.get(delta_key) if delta_key else None,
        delta_good=item.get("delta_good", "up"),
        in_range=None if level == "na" else level == "good",
    )


def _module_for(
    db: Session, principal: Principal, plant_id: uuid.UUID, key: str
) -> tuple[Plant, Module]:
    principal.require("modules.view")
    principal.require("readings.read")
    plant = get_plant_in_scope(db, principal, plant_id)
    module = next(
        (m for m in _visible_modules(db, principal, plant.id, plant.company_id) if m.key == key),
        None,
    )
    if module is None:
        raise NotFoundError("Module not found.")
    return plant, module


def module_trend(
    db: Session, principal: Principal, plant_id: uuid.UUID, key: str, widget: int, hours: int
) -> list[TrendSeries]:
    """The series of one trend widget for another time range (the 6H / 24H / 7D buttons).
    Only the widget's own parameters and its configured ranges can be asked for."""
    plant, module = _module_for(db, principal, plant_id, key)
    widgets = module.layout.get("widgets", [])
    if not 0 <= widget < len(widgets) or widgets[widget].get("type") != "trend_chart":
        raise NotFoundError("Trend chart not found.")
    config = widgets[widget]
    allowed = set(config.get("ranges") or []) | {int(config.get("hours", 24))}
    if hours not in allowed:
        message = "This time range is not available for this chart."
        raise ValidationFailedError(message, [{"field": "hours", "message": message}])
    state = build_state(db, plant, {})
    return _trend(db, state, list(config.get("params") or []), hours)


def module_view(db: Session, principal: Principal, plant_id: uuid.UUID, key: str) -> ModuleView:
    plant, module = _module_for(db, principal, plant_id, key)

    reading = latest_reading(db, plant.id)
    state = build_state(
        db, plant, reading.input_values if reading else {},
        reading.recorded_at if reading else None,
    )  # fmt: skip
    editable = can_edit_readings(db, principal, plant.id)
    rule_results = predicted_problems(db, state)
    plant_alerts = _alerts_for(db, principal, plant.id, state)
    widgets = [
        _widget_view(db, w, state, editable, rule_results, plant_alerts)
        for w in module.layout.get("widgets", [])
    ]
    return ModuleView(
        key=module.key,
        title=module.title,
        reading=summary(db, reading),
        can_edit_readings=editable,
        widgets=widgets,
    )


def _alerts_for(
    db: Session, principal: Principal, plant_id: uuid.UUID, state: PlantState
) -> list[Alert]:
    if not principal.has("alerts.view"):
        return []
    profile = operator_profile(db, principal, plant_id)
    if profile is not None and not profile.show_alerts:
        return []
    return alerts(db, state)


def plant_alerts(db: Session, principal: Principal, plant_id: uuid.UUID) -> PlantAlerts:
    """For the notification bell at the top of every page: alerts and predicted problems.
    An operator whose profile hides alerts gets neither."""
    principal.require("alerts.view")
    plant = get_plant_in_scope(db, principal, plant_id)
    reading = latest_reading(db, plant.id)
    state = build_state(
        db, plant, reading.input_values if reading else {},
        reading.recorded_at if reading else None,
    )  # fmt: skip
    profile = operator_profile(db, principal, plant.id)
    hidden = profile is not None and not profile.show_alerts
    return PlantAlerts(
        reading=summary(db, reading),
        alerts=_alerts_for(db, principal, plant.id, state),
        problems=[] if hidden or reading is None else predicted_problems(db, state).matched,
    )
