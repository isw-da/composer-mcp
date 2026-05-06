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


# ----------------------------------------------------------------------
# UBER_BARS palette helpers
#
# The `Bar Color` variable is the trickiest piece of the UBER_BARS schema.
# Captured shape and gotchas (UAT-verified):
#
# * `Bar Color` MUST contain a metric entry. Setting it to `[]` returns 200
#   on PUT but breaks the visual at render time with
#   "Cannot read properties of undefined (reading 'value')".
#
# * `colorConfig.colors` is an array of `{name, color}` objects, NOT raw
#   hex strings or `{color}`. Strings: "expected JSONObject, found String".
#   Missing name: "required key [name] not found".
#
# * `colorScaleType: 'gradient'` uses the `colors` array as gradient stops.
#   For all-bars-one-colour, supply [{name, color}] with one entry but the
#   renderer may still produce a sequential palette unless you also set
#   `autoColor: false` and `colorSet: 'custom'`.
#
# * When the embed manager passes `theme: '<name>'` at createComponent time,
#   theme palette wins over per-visual palette. Pass `'__platform__'` (or
#   omit) if you want these per-visual edits to take effect in the embed.
# ----------------------------------------------------------------------


def make_bar_color_palette(
    metric_name: str,
    metric_func: str = "sum",
    colors: list[str] | None = None,
    auto_color: bool = False,
    scale_type: str = "gradient",
) -> list[dict]:
    """Build a `Bar Color` variable value with a custom palette.

    `colors` is a plain list of hex strings (e.g. `['#FCE2E5', '#E2001A',
    '#A00012']`) — this helper wraps each into the `{name, color}` shape
    Composer requires.
    """
    palette = colors or ["#E2001A"]
    return [
        {
            "name": metric_name,
            "func": metric_func,
            "colorConfig": {
                "colorNumb": max(3, len(palette)),
                "legendType": "palette",
                "colors": [{"name": f"c{i}", "color": c} for i, c in enumerate(palette)],
                "colorSet": "custom",
                "autoShowColorLegend": False,
                "separateNegativeColor": False,
                "autoColor": auto_color,
                "colorScaleType": scale_type,
            },
        }
    ]


async def set_uber_bars_palette(
    client: ComposerClient,
    visual_id: str,
    metric_name: str,
    colors: list[str],
    metric_func: str = "sum",
    scale_type: str = "gradient",
) -> dict:
    """Replace an UBER_BARS visual's Bar Color palette with the given hex stops.

    Pass 1 colour for a solid look (still gradient-rendered, but uniform).
    Pass 2-3 colours for a brand-aligned ramp (e.g. light pink → red → dark
    red for revenue bars, or red → amber → green for ROAS).
    """
    v = await client.get(f"/visuals/{visual_id}")
    v["source"]["variables"]["Bar Color"] = make_bar_color_palette(
        metric_name, metric_func, colors, auto_color=False, scale_type=scale_type
    )
    return await client.put(f"/visuals/{visual_id}", v)


# ----------------------------------------------------------------------
# KPI conditional formatting
# ----------------------------------------------------------------------


async def set_kpi_conditional_format(
    client: ComposerClient,
    visual_id: str,
    metric_name: str,
    palette: str = "RedYellowGreen",
    thresholds: list[float] | None = None,
    target: str = "metric",
    metric_func: str = "sum",
) -> dict:
    """Apply a conditional-formatting palette to a KPI visual.

    `palette`: a Composer-known palette name. RedYellowGreen is the only
    one that ships universally; tenants may add custom ones.
    `thresholds`: gradient breakpoints between palette colours. For ROAS
    targeting 2.5×, use `[1.0, 2.0]` (red below 1, yellow 1-2, green above).
    `target`: which part of the KPI tile gets coloured: `'metric'` (the
    big number, default) or `'label'` (the title).
    """
    if thresholds is None:
        thresholds = [1.0, 2.0]
    cf = {
        "type": "palette",
        "condition": {
            "type": "metric",
            "metric": {"name": metric_name, "func": metric_func},
        },
        "applyTo": {"type": "namedTargets", "targets": [target]},
        "format": {
            "type": "palette",
            "palette": palette,
            "mode": "gradient",
            "colorNum": 3,
            "thresholds": thresholds,
        },
    }
    v = await client.get(f"/visuals/{visual_id}")
    existing = v.get("source", {}).get("variables", {}).get("Conditional Formatting", [])
    # Replace any existing CF on this metric+target, otherwise append
    existing = [
        e for e in existing
        if not (
            (e.get("condition") or {}).get("metric", {}).get("name") == metric_name
            and target in (e.get("applyTo") or {}).get("targets", [])
        )
    ]
    existing.append(cf)
    v["source"]["variables"]["Conditional Formatting"] = existing
    return await client.put(f"/visuals/{visual_id}", v)


# ----------------------------------------------------------------------
# Variable shape NOT supported in the v25 build we tested
# ----------------------------------------------------------------------
#
# Reference lines on `LINE_AND_BARS` cannot be set via API. The visual's
# `source.variables` keys are exactly: `Y1 Color`, `Y1 Axis`, `Y2 Color`,
# `Y2 Axis`, `Formatting`, `Trend Attribute`. There is no `Reference Line`
# or `Annotations` variable. Composer's UI lets you draw them; the API
# does not (yet) round-trip them.
#
# Saved views / bookmarks return 404 on every reasonable endpoint we
# probed (`/dashboards/{id}/views`, `/bookmarks`, `/states`,
# `/personalizations`, `/views?dashboardId=`). Not exposed in v25.
