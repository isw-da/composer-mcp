"""Theme inspection.

Themes live at `/api/customization/themes` (NOT `/api/themes`, which 404s).
Each theme has an `id`, a `name`, a `masterThemeId` (e.g. `'modern'`,
`'composer'`, `'dark'`, `'__platform__'`), and a `content` blob with two
top-level halves:

* `colors` — the named palette (`brandColor`, `surface`, `onPrimary`,
  `intentPrimary`, ...).
* `customProperties` — per-component overrides keyed by component name.
  The interesting ones for dashboards:
  * `customProperties.charts.KPI.{Background Color, Metric Color, Label Color, ...}`
  * `customProperties.charts.LINE_AND_BARS.{Y1 Color, Y2 Color}`
  * `customProperties.charts.UBER_BARS.{Bar Color}`
  * `customProperties.charts.PIVOT_TABLE.*`
  * `customProperties.colorPalette.colors` — the categorical palette

Write access is gated. PUT/PATCH/POST against `/api/customization/themes`
returns 403 from a tenant-admin session even on tenant-owned themes. So
this module is read-only — for theme content edits ask Symphony ops, or
sidestep by overriding visuals individually (see
`visuals.set_uber_bars_palette`) or overriding chrome via shell CSS in
the embedding app (see `embed/README.md`).

Embed-time theme passing
------------------------
The Composer Embed Manager `createComponent('dashboard', { theme })` accepts
either a theme name (`'otto'`, `'modern'`, `'__platform__'`) or theme id.
When you pass a custom theme its content overrides per-visual palette
settings — so visuals you carefully recoloured may not actually repaint
in the embed. If you want per-visual configs to win, pass
`theme: '__platform__'` and apply branding via shell CSS instead.
"""

from __future__ import annotations

from ..client import ComposerClient


async def list_themes(client: ComposerClient) -> list[dict]:
    """List themes available in the current tenant context.

    Returns `[{id, name, masterThemeId}, ...]` for the in-tenant + system
    themes. System themes have stable ids (`'modern'`, `'composer'`,
    `'dark'`, `'d+a_light'`, `'__platform__'`).
    """
    items = await client.get_list("/customization/themes")
    return [
        {
            "id": t.get("id"),
            "name": t.get("name"),
            "masterThemeId": t.get("masterThemeId"),
            "system": t.get("system", False),
        }
        for t in items
        if isinstance(t, dict)
    ]


async def get_theme(client: ComposerClient, theme_id: str) -> dict:
    """Fetch the full theme record (content included)."""
    return await client.get(f"/customization/themes/{theme_id}")


async def describe_theme_palette(client: ComposerClient, theme_id: str) -> dict:
    """Convenience: pull just the parts of a theme that drive chart colour."""
    t = await get_theme(client, theme_id)
    cp = (t.get("content") or {}).get("customProperties", {})
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "masterThemeId": t.get("masterThemeId"),
        "colors": (t.get("content") or {}).get("colors"),
        "colorPalette": cp.get("colorPalette"),
        "charts": cp.get("charts"),
    }
