"""Visual creation, retrieval, and update.

Visuals are charts/widgets that reference a source and a set of fields.
Each visual can only belong to ONE dashboard — the API rejects sharing a
visual across dashboards with "visuals already used in other dashboards".
Use `create_visual_pair()` to build a TOP-level twin (Visual Gallery) and
an IN_DASHBOARD twin (for embedding) from the same template.

UAT-side variable shape constraints (real failures observed, fix in this
shape OR Composer 400s with "extraneous key not permitted"):

* **KPI** (`Metric`, `Comparison Metric`): `{name, func}` only. Adding
  `label` is rejected.

* **UBER_BARS** (`Multi Group By` sort): `{name, dir, label, type:'METRIC'}`.
  Adding `func: 'sum'` here is rejected even though metric-typed sort logically
  needs an aggregator. Composer infers it from the `Metric` variable.

* **PIVOT_TABLE** buckets are `Row Attributes`, `Column Attributes`, `Metrics`
  — NOT `Rows`, `Columns`, `Metric`. Setting the wrong bucket names is
  silently accepted on POST but the visual renders with default content
  (often `partner_segment` rows in our case) instead of your config.

* **LINE_AND_BARS** has `Trend Attribute` (a list whose first element is the
  X-axis attribute) and `Y Axis` (a list of metric variables).

* **LIST_FILTER** has `Display Value` with TWO entries: the field to filter
  on, then a `{name: 'none'}` placeholder. See `composer_create_visual_pair`.

When in doubt: GET `/sources/{id}/visual-types/{vtId}/initial-visual` and
print `tpl.source.variables` keys before editing.
"""

from __future__ import annotations

from ..client import ComposerClient


# --------------------------------------------------------------------
# Bucket name reference — what each visual type's `source.variables`
# keys are called. Captured to save a round trip every time.
# --------------------------------------------------------------------

PIVOT_BUCKETS = {
    "rows": "Row Attributes",
    "columns": "Column Attributes",
    "metrics": "Metrics",
}

KPI_BUCKETS = {
    "metric": "Metric",
    "comparison_metric": "Comparison Metric",
}

UBER_BARS_BUCKETS = {
    "group": "Multi Group By",
    "metric": "Metric",
    "bar_color": "Bar Color",
}

LINE_AND_BARS_BUCKETS = {
    "trend_attribute": "Trend Attribute",
    "y_axis": "Y Axis",
}

LIST_FILTER_BUCKETS = {
    "display_value": "Display Value",
}


async def list_visuals(client: ComposerClient) -> list[dict]:
    items = await client.get_list("/visuals")
    return [
        {
            "id": v["id"],
            "name": v.get("visualName") or v.get("name"),
            "type": v.get("type"),
            "level": v.get("level"),
            "sourceId": (v.get("source") or {}).get("sourceId"),
        }
        for v in items
        if isinstance(v, dict)
    ]


async def get_visual(client: ComposerClient, visual_id: str) -> dict:
    return await client.get(f"/visuals/{visual_id}")


async def create_visual(client: ComposerClient, visual_template: dict) -> dict:
    """Create a visual from a (modified) initial-visual template.

    Pass `level` explicitly:
      - `'TOP'`: visual lives in Visual Gallery, browseable standalone
      - `'IN_DASHBOARD'`: visual is scoped to one dashboard

    Best practice: build the TOP version first (so it appears in the Gallery),
    then call `clone_for_dashboard` to produce the IN_DASHBOARD copy when
    embedding it in a dashboard. See `create_visual_pair` below.
    """
    visual_template.pop("id", None)
    return await client.post("/visuals", visual_template)


async def clone_for_dashboard(client: ComposerClient, top_visual_id: str) -> dict:
    """Clone a TOP-level visual into an IN_DASHBOARD copy.

    Composer requires every dashboard widget to reference an IN_DASHBOARD-level
    visual that is unique to that dashboard. This helper fetches the TOP twin,
    duplicates it with level changed to IN_DASHBOARD, and returns the new id.
    """
    src = await client.get(f"/visuals/{top_visual_id}")
    src.pop("id", None)
    src["level"] = "IN_DASHBOARD"
    return await client.post("/visuals", src)


async def create_visual_pair(client: ComposerClient, visual_template: dict) -> dict:
    """Create both a TOP twin (Gallery-browseable) and an IN_DASHBOARD twin
    (for embedding) from one template. Returns {"top_id": ..., "dashboard_id": ...}.
    """
    import copy as _copy
    visual_template.pop("id", None)
    top_template = _copy.deepcopy(visual_template)
    top_template["level"] = "TOP"
    top = await client.post("/visuals", top_template)

    dash_template = _copy.deepcopy(visual_template)
    dash_template["level"] = "IN_DASHBOARD"
    dash = await client.post("/visuals", dash_template)

    return {"top_id": top["id"], "dashboard_id": dash["id"]}


async def delete_visual(client: ComposerClient, visual_id: str) -> dict:
    await client.delete(f"/visuals/{visual_id}")
    return {"deleted": visual_id}
