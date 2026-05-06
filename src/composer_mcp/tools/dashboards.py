"""Dashboard creation and layout.

Dashboards are containers of widgets. Each widget binds to a visualId and
positions it in a grid. The dashboard layout uses 2-element path/params
arrays in Composer v25 (NOT 4-element).

Field links — the mechanism that scopes a filter widget's selection across
all consumer widgets — use the `FieldLinkResource` shape:
    {label: "Campaign Type",
     mappings: [{sourceId: "...", fieldName: "campaign_type"}]}
NOT `{name, fields}` as some older docs imply. See `make_field_link`.

Time scope — to override the per-visual default 7-day window so all widgets
share a synchronised window, set each visual's `controlsCfg.timeControlCfg`
to `{from, to, timeField}`. Special tokens:
    +$start_of_data, +$end_of_data
    +$end_of_data_-1_week, +$end_of_data_-1_month, etc.
There's also a dashboard-level `unifiedBarCfgs` that sets up a shared time
slider — but it must be added via PUT after create (passing it on POST
triggers HV000028 Hibernate validation).
"""

from __future__ import annotations

import secrets
from typing import Any

from ..client import ComposerClient


def widget_id() -> str:
    """Generate a 32-char hex widget ID matching Composer's expected format."""
    return secrets.token_hex(16)


def make_field_link(label: str, source_id: str, field_name: str) -> dict:
    """Build the `FieldLinkResource` shape for a single field link.

    A dashboard's `fieldLinks` is a list of these. Each describes one named
    cross-widget filter dimension (e.g. "Campaign Type") and which source
    field carries it. When a filter widget changes its selection, every
    consumer widget that has the same source field is rescoped automatically.
    """
    return {
        "label": label,
        "mappings": [{"sourceId": source_id, "fieldName": field_name}],
    }


async def list_dashboards(client: ComposerClient) -> list[dict]:
    items = await client.get_list("/dashboards")
    return [
        {
            "id": d["id"],
            "name": d.get("name"),
            "widgetCount": len((d.get("dashboardLayout") or {}).get("layout", [])),
        }
        for d in items
        if isinstance(d, dict)
    ]


async def get_dashboard(client: ComposerClient, dashboard_id: str) -> dict:
    return await client.get(f"/dashboards/{dashboard_id}")


async def create_dashboard(
    client: ComposerClient,
    name: str,
    widgets: list[dict],
    description: str = "",
    is_responsive: bool = True,
    is_free_form: bool = False,
) -> dict:
    """Create a dashboard.

    Each widget dict must already include:
      - id (32-char hex; use widget_id() helper)
      - name, description
      - visualId (from a previously POSTed visual)
      - layout: { row, col, rowSpan, colSpan }

    The layout grid (dashboardLayout.layout) is computed from the widget list
    using widget.id as widgetId and inferring path/params from the layout
    block. Pass an explicit `dashboard_layout` via update_dashboard_layout if
    you need a non-default placement.

    NEVER include unifiedBarCfgs in the create payload — it triggers
    HV000028 Hibernate validation errors. Add it via update after create.
    """
    layout_entries = []
    for i, w in enumerate(widgets):
        wid = w["id"]
        layout = w.get("layout", {})
        row = layout.get("row", i)
        col = layout.get("col", 0)
        h_pct = max(10, min(100, int(layout.get("rowSpan", 6) * 5)))
        w_pct = max(10, min(100, int(layout.get("colSpan", 16) * 5)))
        layout_entries.append({"widgetId": wid, "path": [row, col], "params": [h_pct, w_pct]})

    body = {
        "name": name,
        "description": description,
        "layout": "unset",
        "dashboardLayout": {
            "layout": layout_entries,
            "locked": [],
            "isResponsive": is_responsive,
            "isFreeForm": is_free_form,
        },
        "showDescription": False,
        "isReportDashboard": False,
        "fieldLinks": [],
        "rowFilters": [],
        "mutedLinks": [],
        "widgets": [_normalise_widget(w) for w in widgets],
        "tags": [],
    }
    return await client.post("/dashboards", body)


def _normalise_widget(w: dict[str, Any]) -> dict[str, Any]:
    """Make sure widget dict has all required fields per the skill."""
    if "id" not in w:
        raise ValueError("Widget missing 'id' (use widget_id() helper)")
    if "visualId" not in w:
        raise ValueError(f"Widget {w.get('name', '?')} missing 'visualId'")
    return {
        "id": w["id"],
        "name": w.get("name", ""),
        "description": w.get("description", ""),
        "header": w.get("header", {"visibility": "VISIBLE"}),
        "layout": w.get("layout", {"col": 1, "row": 1, "rowSpan": 6, "colSpan": 16}),
        "visualId": w["visualId"],
        "content": {"contentType": "VISUAL", "visualId": w["visualId"]},
        "pickers": w.get("pickers", {"hiddenPickers": [], "visibility": "VISIBLE"}),
    }


async def update_dashboard_layout(
    client: ComposerClient, dashboard_id: str, layout: list[dict]
) -> dict:
    """Replace the dashboardLayout.layout grid for an existing dashboard.

    `dashboardLayout.layout` is the SOURCE OF TRUTH for widget positioning.
    Each widget's per-widget `layout` field (rowSpan/colSpan) is vestigial —
    Composer reads it from layout entries shaped:

        {widgetId, path: [row, col], params: [height_pct, width_pct]}

    height_pct and width_pct are percentages of the dashboard, NOT grid
    cells. A KPI tile is typically [14, 16]. A trend chart [40, 100]. A
    LIST_FILTER above content widgets is [25-30, 100] to give it room to
    show options without scrolling. Setting [6, 33] (the agent's mistake)
    squashes the filter into a near-invisible strip.
    """
    current = await get_dashboard(client, dashboard_id)
    current["dashboardLayout"]["layout"] = layout
    return await client.put(f"/dashboards/{dashboard_id}", current)


async def resize_widget_in_layout(
    client: ComposerClient,
    dashboard_id: str,
    widget_id: str,
    height_pct: int,
    width_pct: int,
) -> dict:
    """Bump a single widget's size (height %, width %) in dashboardLayout.

    Common cases:
      * Filter widget too small to show options: 30, 100
      * KPI tile in a 6-across row: 14, 16
      * Full-width trend chart: 40, 100
      * Pivot in a 2-across row: 30, 50
    """
    d = await get_dashboard(client, dashboard_id)
    layout = (d.get("dashboardLayout") or {}).get("layout") or []
    found = False
    for item in layout:
        if item.get("widgetId") == widget_id:
            item["params"] = [height_pct, width_pct]
            found = True
    if not found:
        raise ValueError(f"widget {widget_id} not found in dashboard {dashboard_id} layout")
    return await client.put(f"/dashboards/{dashboard_id}", d)


async def resize_widgets_by_visual_type(
    client: ComposerClient,
    dashboard_id: str,
    visual_type: str,
    height_pct: int,
    width_pct: int,
    visual_type_lookup: dict[str, str] | None = None,
) -> dict:
    """Resize every widget on a dashboard whose backing visual matches
    `visual_type` (e.g. `'LIST_FILTER'`, `'KPI'`, `'UBER_BARS'`).

    Pass `visual_type_lookup` (a `{widget_id: visual_type}` map you already
    have) to skip a fetch per visual. Otherwise this calls
    `/visuals/{id}` for each widget.
    """
    d = await get_dashboard(client, dashboard_id)
    if visual_type_lookup is None:
        visual_type_lookup = {}
        for w in d.get("widgets") or []:
            vid = w.get("visualId") or (w.get("content") or {}).get("visualId")
            if not vid:
                continue
            v = await client.get(f"/visuals/{vid}")
            visual_type_lookup[w["id"]] = v.get("type")
    touched = []
    for item in (d.get("dashboardLayout") or {}).get("layout") or []:
        if visual_type_lookup.get(item["widgetId"]) == visual_type:
            item["params"] = [height_pct, width_pct]
            touched.append(item["widgetId"])
    if not touched:
        return {"updated": 0, "note": f"no {visual_type} widgets on this dashboard"}
    await client.put(f"/dashboards/{dashboard_id}", d)
    return {"updated": len(touched), "widgetIds": touched}


async def delete_dashboard(client: ComposerClient, dashboard_id: str) -> dict:
    await client.delete(f"/dashboards/{dashboard_id}")
    return {"deleted": dashboard_id}
