"""Dashboard creation and layout.

Dashboards are containers of widgets. Each widget binds to a visualId and
positions it in a grid. The dashboard layout uses 2-element path/params
arrays in Composer v25 (NOT 4-element).
"""

from __future__ import annotations

import secrets
from typing import Any

from ..client import ComposerClient


def widget_id() -> str:
    """Generate a 32-char hex widget ID matching Composer's expected format."""
    return secrets.token_hex(16)


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
    """Replace the dashboardLayout.layout grid for an existing dashboard."""
    current = await get_dashboard(client, dashboard_id)
    current["dashboardLayout"]["layout"] = layout
    return await client.put(f"/dashboards/{dashboard_id}", current)


async def delete_dashboard(client: ComposerClient, dashboard_id: str) -> dict:
    await client.delete(f"/dashboards/{dashboard_id}")
    return {"deleted": dashboard_id}
