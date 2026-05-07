"""Dashboard templates — opinionated starting points for common patterns.

These compose existing primitives (visuals, dashboards, custom metrics)
into ready-to-iterate-on demo dashboards. They are deliberately
**opinionated**: the BI agent's "phase 2 sketch" is encoded as a working
default, not a billion-knob configurator. Edit the resulting dashboard
afterwards via the regular dashboard helpers.

Templates available:

* `generate_snapshot_dashboard(source_id, name, metrics, trend_metric)` —
  the UC1 "Today at a glance" pattern: a campaign-type filter, a row of
  KPI tiles for the named metrics, and a bar+line trend chart binding
  one metric vs another.
"""

from __future__ import annotations

import secrets
from typing import Any

from ..client import ComposerClient
from . import dashboards, sources, visuals


# Default tile configuration for a snapshot dashboard. Each entry produces
# one KPI tile bound to a metric on the source.
DEFAULT_KPI_PRESETS = {
    "Impressions":     {"field": "impressions",  "func": "sum"},
    "Clicks":          {"field": "clicks",       "func": "sum"},
    "Sales (EUR)":     {"field": "sales_eur",    "func": "sum",
                         "format": "EUR"},
    "Ad Spend (EUR)":  {"field": "ad_spend_eur", "func": "sum",
                         "format": "EUR"},
    "Conversion Rate": {"field": "conversion_rate", "func": "avg",
                         "format": "PERCENT"},
    "ROAS":            {"field": "roas", "func": "avg",
                         "format": "RATIO",
                         "conditional_format": True,
                         "thresholds": [1.0, 2.0]},
}


async def generate_snapshot_dashboard(
    client: ComposerClient,
    source_id: str,
    name: str,
    description: str = "",
    kpis: list[str] | None = None,
    filter_field: str | None = "campaign_type",
    trend_field: str | None = "date",
    trend_y1: tuple[str, str] | None = ("sales_eur", "sum"),
    trend_y2: tuple[str, str] | None = ("ad_spend_eur", "sum"),
    brand_color: str = "#E2001A",
    secondary_color: str = "#1A1A1A",
) -> dict:
    """Build the UC1 "Today at a glance" snapshot dashboard.

    Layout:
      * row 0: LIST_FILTER on `filter_field` (full width, 25% height)
      * row 1: KPI tiles for each metric in `kpis` (each 14% × ~16% width)
      * row 2: LINE_AND_BARS trend chart, Y1 = trend_y1 (bars, brand_color),
        Y2 = trend_y2 (line, secondary_color), full width

    Returns: `{dashboard_id, dashboard_url_id, widgets: [{name, widget_id,
    visual_id, type}], skipped: [<kpi names that lacked the source field>]}`.

    The trend chart and KPIs all bind to the SAME source. If you don't have
    a `campaign_type` field, pass `filter_field=None` to skip the filter
    widget. If a KPI's underlying field doesn't exist on the source, it's
    skipped (with a note in the return value) rather than failing the whole
    build.
    """
    kpis = kpis or list(DEFAULT_KPI_PRESETS)[:6]

    # Probe the source so we can skip widgets pointing at missing fields.
    fields = await sources.get_source_fields(client, source_id)
    field_names = {(f.get("name") or "").lower() for f in fields}

    def have(name: str) -> bool:
        return name.lower() in field_names

    skipped = []
    layout_entries: list[dict[str, Any]] = []
    widgets_for_create: list[dict[str, Any]] = []
    widgets_summary: list[dict[str, Any]] = []

    # 1) Filter widget at top
    if filter_field and have(filter_field):
        f_visual = await _make_filter_visual(client, source_id, filter_field)
        wid = dashboards.widget_id()
        widgets_for_create.append({
            "id": wid,
            "name": filter_field.replace("_", " ").title(),
            "description": "",
            "visualId": f_visual["id"],
        })
        widgets_summary.append({
            "name": filter_field, "widget_id": wid,
            "visual_id": f_visual["id"], "type": "LIST_FILTER",
        })
        layout_entries.append({"widgetId": wid, "path": [0, 0], "params": [25, 100]})
    elif filter_field:
        skipped.append(f"filter:{filter_field}")

    # 2) KPI row
    col_each = max(8, 96 // max(1, len(kpis)))
    for i, kpi_name in enumerate(kpis):
        preset = DEFAULT_KPI_PRESETS.get(kpi_name)
        if not preset or not have(preset["field"]):
            skipped.append(f"kpi:{kpi_name}")
            continue
        v = await _make_kpi_visual(client, source_id, kpi_name, preset, brand_color)
        wid = dashboards.widget_id()
        widgets_for_create.append({
            "id": wid, "name": kpi_name, "description": "",
            "visualId": v["id"],
        })
        widgets_summary.append({
            "name": kpi_name, "widget_id": wid,
            "visual_id": v["id"], "type": "KPI",
        })
        layout_entries.append({
            "widgetId": wid, "path": [1, i],
            "params": [14, col_each],
        })

    # 3) Trend chart
    if (
        trend_field and have(trend_field)
        and trend_y1 and have(trend_y1[0])
        and trend_y2 and have(trend_y2[0])
    ):
        t_visual = await _make_trend_visual(
            client, source_id,
            trend_field=trend_field,
            y1=trend_y1, y2=trend_y2,
            y1_color=brand_color, y2_color=secondary_color,
        )
        wid = dashboards.widget_id()
        widgets_for_create.append({
            "id": wid, "name": f"{trend_y1[0]} vs {trend_y2[0]} - daily trend",
            "description": "", "visualId": t_visual["id"],
        })
        widgets_summary.append({
            "name": "trend", "widget_id": wid,
            "visual_id": t_visual["id"], "type": "LINE_AND_BARS",
        })
        layout_entries.append({
            "widgetId": wid, "path": [2, 0], "params": [40, 100],
        })
    else:
        skipped.append("trend")

    # Compose the dashboard
    body = {
        "name": name,
        "description": description,
        "layout": "unset",
        "dashboardLayout": {
            "layout": layout_entries,
            "locked": [],
            "isResponsive": True,
            "isFreeForm": False,
        },
        "showDescription": False,
        "isReportDashboard": False,
        "fieldLinks": (
            [dashboards.make_field_link(
                filter_field.replace("_", " ").title(),
                source_id,
                filter_field,
            )]
            if filter_field and have(filter_field)
            else []
        ),
        "rowFilters": [],
        "mutedLinks": [],
        "widgets": [_normalise_widget(w) for w in widgets_for_create],
        "tags": [],
    }
    created = await client.post("/dashboards", body)

    return {
        "dashboard_id": created.get("id"),
        "name": name,
        "widgets": widgets_summary,
        "skipped": skipped,
        "note": (
            "Edit further via update_dashboard_layout, resize_widget_in_layout, "
            "set_kpi_conditional_format, set_uber_bars_palette."
        ),
    }


def _normalise_widget(w: dict) -> dict:
    return {
        "id": w["id"],
        "name": w.get("name", ""),
        "description": w.get("description", ""),
        "header": {"visibility": "VISIBLE"},
        "layout": {"col": 1, "row": 1, "rowSpan": 6, "colSpan": 16},
        "visualId": w["visualId"],
        "content": {"contentType": "VISUAL", "visualId": w["visualId"]},
        "pickers": {"hiddenPickers": [], "visibility": "VISIBLE"},
    }


async def _get_visual_type_id(
    client: ComposerClient, source_id: str, type_name: str
) -> str:
    """Resolve the platform visualTypeId for a generic type name on this source."""
    types = await sources.get_source_visual_types(client, source_id)
    for t in types:
        if (t.get("type") or "").upper() == type_name.upper():
            return t.get("id") or t.get("visualTypeId")
    raise ValueError(
        f"source {source_id} doesn't expose visual type {type_name!r}; "
        f"available: {[t.get('type') for t in types]}"
    )


async def _make_filter_visual(
    client: ComposerClient, source_id: str, field: str
) -> dict:
    vt_id = await _get_visual_type_id(client, source_id, "LIST_FILTER")
    tpl = await sources.get_initial_visual(client, source_id, vt_id)
    label = field.replace("_", " ").title()
    tpl["source"]["variables"]["Display Value"] = [
        {"name": field, "label": label, "type": "ATTRIBUTE",
         "limit": 10000, "sort": {"dir": "asc", "label": label,
                                   "name": field, "type": "ATTRIBUTE"}},
        {"name": "none", "limit": 10000, "sort": {"dir": "asc", "name": "none"}},
    ]
    tpl["visualName"] = label
    tpl["level"] = "IN_DASHBOARD"
    return await visuals.create_visual(client, tpl)


async def _make_kpi_visual(
    client: ComposerClient,
    source_id: str,
    name: str,
    preset: dict,
    brand_color: str,
) -> dict:
    vt_id = await _get_visual_type_id(client, source_id, "KPI")
    tpl = await sources.get_initial_visual(client, source_id, vt_id)
    field, func = preset["field"], preset["func"]
    tpl["source"]["variables"]["Metric"] = [{"name": field, "func": func}]
    if preset.get("conditional_format"):
        tpl["source"]["variables"]["Conditional Formatting"] = [{
            "type": "palette",
            "condition": {"type": "metric", "metric": {"name": field, "func": func}},
            "applyTo": {"type": "namedTargets", "targets": ["metric"]},
            "format": {
                "type": "palette", "palette": "RedYellowGreen",
                "mode": "gradient", "colorNum": 3,
                "thresholds": preset.get("thresholds", [1.0, 2.0]),
            },
        }]
    tpl["visualName"] = name
    tpl["level"] = "IN_DASHBOARD"
    return await visuals.create_visual(client, tpl)


async def _make_trend_visual(
    client: ComposerClient,
    source_id: str,
    trend_field: str,
    y1: tuple[str, str],
    y2: tuple[str, str],
    y1_color: str,
    y2_color: str,
) -> dict:
    vt_id = await _get_visual_type_id(client, source_id, "LINE_AND_BARS")
    tpl = await sources.get_initial_visual(client, source_id, vt_id)
    tpl["source"]["variables"]["Trend Attribute"] = [
        {"name": trend_field, "label": trend_field.title(), "type": "ATTRIBUTE"}
    ]
    tpl["source"]["variables"]["Y Axis"] = [
        {"name": y1[0], "func": y1[1]},
        {"name": y2[0], "func": y2[1]},
    ]
    tpl["source"]["variables"]["Y1 Color"] = y1_color
    tpl["source"]["variables"]["Y2 Color"] = y2_color
    tpl["visualName"] = f"{y1[0]} vs {y2[0]} trend"
    tpl["level"] = "IN_DASHBOARD"
    return await visuals.create_visual(client, tpl)
