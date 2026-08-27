# Composer theme JSON notes

The theme-authoring reference for Composer v25. Everything here is empirical,
worked out against UAT while building brand themes and diffing what the UI
sent. Documented so the next person doesn't wipe a theme to `{}` and burn an
afternoon finding out why.

> **Heads up on writes.** This MCP wraps themes read-only
> (`composer_list_themes`, `composer_get_theme`,
> `composer_describe_theme_palette`). Theme content WRITES (PUT/POST) 403
> from a tenant-admin session even on a theme that tenant created. See
> `LIMITATIONS.md` -> "Theme content writes" for the three ways out (pass
> `theme: '__platform__'` and brand via shell CSS, or ask Symphony global
> admin to apply the edits). This file is the schema reference for when you
> CAN write, or when you need to read a theme and understand its shape.

## Top-level structure

A theme record is `{name, content}`. Everything that matters lives under
`content`, in three sections.

| Section | Controls |
|---|---|
| `variables` | Design tokens. Colours, fonts, sizes, palettes, radii. The foundation layer everything else references via `$colors.*`. |
| `customProperties` | Per-component UI overrides. Resolves tokens from `variables.colors` via `$colors.tokenName`, or takes literal `#hex` / `rgba()`. |
| `symphony` | The embedded Simba Intelligence chatbot layer. Optional, but if absent the chatbot ignores the theme entirely and falls back to internal defaults (looks unstyled). |

`variables.colors` carries the named palette: `primary`, `secondary`,
`brandColor`, `surface`, `background`, `text`, `onPrimary`, the full
`intent*` family (primary/success/warning/danger/base/minimal plus their
hover/active/disabled/background states), and so on. Other entries reference
these as `$colors.brandColor`.

`variables.palettes` carries the chart palettes: `DefaultSequential` (keyed
by series count 2-9) and, optionally, the four KPI palettes below.

`customProperties` sections you will touch most: `dashboard.*`, `widget.*`,
`navbar.*`, `charts.base.*`, `charts.KPI.*`, `charts.{TYPE}.*`,
`buttons.*`, `tables.base.*`, `timebar.*`, `metaDataPicker.*`,
`visualEditor.*`.

`symphony` has its own `variables.colors` token namespace (separate from the
top-level one, you cannot cross-reference between them) plus
`symphony.components.chatBot`, `buttons`, `input`, `actionCard`, `sidebar`.

For the key structure only, see
`logi-composer-theme-template.json` in the toolkit (annotated with
`BRAND_*` placeholders). Do not copy a deployed customer theme as a starting
point for a different brand.

## The content-wrapper PUT gotcha

The single most expensive mistake. The PUT body MUST wrap everything inside
a `content` key, exactly like POST:

```json
{
  "name": "<theme-name>",
  "content": {
    "variables": { ... },
    "customProperties": { ... },
    "symphony": { ... }
  }
}
```

If you pass `variables`, `customProperties`, or `symphony` at the TOP level
(outside `content`), the server returns 200 OK and stores `"content": {}`.
The theme is silently wiped. No error, no warning, just an empty theme and
unstyled dashboards.

Always verify the write landed: re-read the theme and confirm `content` is
non-empty.

## KPI palettes (the four)

Four KPI palettes live under `variables.palettes`. KPI visuals use them
through Conditional Formatting rules to colour tile backgrounds and metric
text by performance.

They are not mandatory. The deployed Tetra Pak theme ships
`palettes: ['DefaultSequential']` alone and renders fine; KPI conditional
formatting simply has nothing to offer in that theme. Include all four if
you want performance colouring, and treat any of them as absent when
reading someone else's theme.

| Palette | Applied to | Direction |
|---|---|---|
| `KPIBackgroundGradient` | Tile background | bad -> neutral -> good |
| `KPIBackgroundGradientReverse` | Tile background | good -> neutral -> bad |
| `KPIMetricGradient` | Metric text | bad -> neutral -> good |
| `KPIMetricGradientReverse` | Metric text | good -> neutral -> bad |

Each palette is an object keyed `"2"` through `"9"` (matching the CF rule's
`colorNum`), each value an array of hex strings of that length. The gradient
is symmetric: bold colour at each end, neutral at the centre. The reverse
palettes are the exact index-reversal of the base, for KPIs where lower is
better (cost, error rate, churn): swap index 0 with last, 1 with
second-to-last, and so on.

> Palette values do NOT support `rgba()`. Every entry must be an opaque hex
> string. Any transparency attempt is ignored.

### Derivation maths

Background palettes are light/pastel so they never overwhelm tile content.
Blend each endpoint colour toward white at 15% intensity, per channel:

```
blended_channel = round((1 - 0.15) * 255 + 0.15 * channel)
```

- Danger end: 15% of `intentDanger` into white -> light pastel red.
- Success end: 15% of `intentSuccess` into white -> light pastel green.
- Neutral centre: `#F5F5F5`.
- Intermediate stops: blend at 5%, 10%, 12% as you move from each endpoint
  toward the centre.

Worked example for a brand danger of `#<danger-hex>` (channels R, G, B):

```
R' = round(0.85 * 255 + 0.15 * R)
G' = round(0.85 * 255 + 0.15 * G)
B' = round(0.85 * 255 + 0.15 * B)
```

Metric palettes are bold/saturated: use the full, undiluted `intentDanger`
and `intentSuccess` as endpoints, bridge through neutral grey (`#888888`) at
the midpoint, with intermediate steps blending the primary colour toward
grey. Keep customer colours out of source control: use placeholders like
`#<brand-danger-hex>` / `#<brand-success-hex>` when documenting a specific
theme.

## KPI conditional formatting (the dark-tile trap)

A `charts.KPI."Background Color"` variable alone will NOT override dark
themes. KPI tiles render with a dark background and the value text comes out
invisible, four dark grey boxes with nothing in them.

The fix is to set Conditional Formatting on the KPI visual with
`condition.type: "always"`, targeting `background`, `label`,
`comparisonData`, `upArrowColor`, and `downArrowColor`. At minimum:

- `Conditional Formatting` background `#ffffff`, label `#9b9b9b` (or your
  brand text colour).
- `Comparison Metric: [{"name": "none"}]` (not `[]`) when no comparison.
- `Comparison.mode: "off"` (not `"value"`) when no comparison.
- Supply all the colour variables: `Label Color`, `Metric Color`,
  `Background Color`, `Up Arrow Color`, `Down Arrow Color`,
  `Comparison Data Color`, `Apply Formatting To`, `Color Metric`.

The visual-side bucket names for KPI live in `SCHEMA_NOTES.md` ->
"Visuals". This is the theme-side counterpart: the palettes exist in the
theme, the CF rule on the visual pulls them in.

## Timebar opaque-hex bug

Sliding the timebar scrubber doubles the period labels (e.g. "Q4 2025"
rendered twice on top of itself, looking bold or blurred). The scrubber
draws on an HTML canvas; when `timebar.scrubber.backgroundColor` resolves to
a semi-transparent `rgba()`, the selected-range canvas does not fully cover
the background canvas and both label sets show through.

Fix: all timebar background properties must be opaque hex. Never `rgba()`,
and never a `$colors.*` token that resolves to `rgba()` (e.g. an intent
background token at 10% alpha). The three to check:

```json
"timebar": {
  "backgroundColorHover": "#<opaque-hex>",
  "scrubber": {
    "backgroundColor": "#<opaque-hex>",
    "backgroundColorHover": "#<opaque-hex>"
  }
}
```

To preserve a semi-transparent brand tint, composite it onto the timebar
background and store the resulting opaque equivalent.

### metaDataPicker contrast

The dimension/measure picker defaults `metaDataPicker.background` to
`$colors.backgroundVariant`, which on light themes sits too close to the
white widget tiles (`$colors.surface`) and disappears. Set the picker
background noticeably darker than the surface (a medium grey on light
themes), and make `metaDataPicker.color` / `secondary` high-contrast against
it. Keep `item.border` / `item.aggrHover` / `item.hover.bg` consistent with
the picker background.

## Blank grey panels (schema mismatch)

Different Composer instances and versions use different `customProperties`
schemas: different property names, nesting depth, key conventions. If a
theme's `customProperties` uses names or structures the target instance does
not recognise, the renderer silently fails to build those UI controls. The
visual-editor sidebar panels (Color, Settings, Filter) render as blank grey
rectangles. Charts, widgets, navbar, buttons may all render fine, so it is
easy to miss.

Known shape differences between schemas (illustrative, confirm against your
target): `buttons.*.background` vs `bg`, `card`/`widget`/`visualEditor`
`border` vs `borderColor`, `checkbox.checked` flat string vs nested object.
The point is not the specific deltas, it is that you cannot assume.

### Reference-theme workflow

Never build a theme by copying `customProperties` from a template, an
example file, or a different instance. Always:

1. `GET /api/customization/themes/{reference_id}` against the EXACT instance
   you will deploy to (use `composer_get_theme`). Pick a known-good custom
   theme that already renders correctly there.
2. Deep-copy its `content.customProperties` structure. Keep every key,
   nesting level, and section as-is.
3. Replace `content.variables` with your brand tokens (colours, fonts,
   `palettes.DefaultSequential`, radii).
4. In `customProperties`, change only VALUES, never property names, nesting
   depth, or which sections exist. Every `$colors.tokenName` must resolve to
   a key in `variables.colors`; a dangling reference is another silent
   render failure.
5. Audit text contrast on light-surface themes. Reference themes from
   dark instances hardcode white text (`#FFFFFF`, `#fff`,
   `rgb(255,255,255)`, or near-invisible `rgb(255,255,255, 0.01)`) on keys
   like `widget.label.color`, `widget.titleColor`,
   `dashboard.header.text`. On a white surface that text vanishes. Switch
   those to `$colors.text`. Leave white text where it belongs, on dark
   sections (`navbar`, `popover.title`, `tooltip`, brand banner).
6. Ensure the timebar background props are opaque hex (above).
7. PUT/POST, reload a dashboard, and check the three sidebar panels render
   and the timebar labels are not doubled.

Fetch the reference fresh each time; the schema can shift with platform
updates. Diff your draft against the known-good reference before you write,
not after.

## Timebar full range

Unrelated to the opaque-hex bug above, this one is about the source's global
time settings, not the theme. Default the timebar to the full dataset range
so dashboards show all data rather than a hidden subset. When configuring a
source's global settings:

```json
{ "from": "+$start_of_data", "to": "+$end_of_data" }
```

Only narrow the range when the user explicitly asks. A narrower default
silently hides rows and looks like missing data.

## Sources

- Empirical theme guides in the Composer toolkit (`Styling/`), worked out
  against UAT: the theme JSON schema, the KPI palette derivation, the
  content-wrapper PUT behaviour, the timebar canvas bug, and the
  blank-grey-panel schema-mismatch workflow.
- KPI conditional-formatting requirement and timebar full-range default:
  verified in build sessions and recorded in the project memory feedback
  notes.
- Branding and customisation surface for embeds is covered on the Confluence
  Embed API page:
  https://insightsoftware.atlassian.net/wiki/spaces/DCI/pages/15750987797/Embed+API
  The theme-content gotchas above are not in the official docs; they are
  presented from the empirical guides.
