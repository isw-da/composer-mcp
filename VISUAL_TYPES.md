# Composer visual types: API-side configuration

Absorbed from Peter Armstrong's toolkit, 27 August 2026, source
`~/logi-composer/peter-kb/bundle-2026-05-21/logi-composer-toolkit/docs/Composer-Visual-Types-Guide.md`.

## What this file is for

`SCHEMA_NOTES.md` (Visuals section) already carries the variable-bucket names
and the field-shape gotchas for KPI, UBER_BARS, LINE_AND_BARS, PIVOT_TABLE,
LIST_FILTER, ARC, BULLET_GAUGE, COMBO_CHART and HISTOGRAM. The 255 product
articles under
`~/si-docs-mirror/logi-composer-current/v26/articles/use-dashboards-and-visuals-in-composer-26/`
cover how each chart behaves in the UI (`43701212397069-kpi-charts.md`,
`43701131102477-pivot-tables.md`, `43701178280461-heat-maps.md`,
`43701212621197-packed-bubble-charts.md`, `43701130594573-donut-charts.md`,
`43701212168461-floating-bubble-charts.md` and the rest). Neither of those
gives you the **visual type ID** you must post, nor the settings-object shapes
that sit alongside the metric buckets. That is what is recorded here.

## The visual type ID quick reference

Peter's table, `Composer-Visual-Types-Guide.md:654-670`. Each row is the hex
identifier you pass as `visualTypeId` on `POST /api/visuals`, with the bucket
that carries the measure and the bucket that carries colour.

| Type | visualTypeId | Key metric variable | Key colour variable |
|---|---|---|---|
| UBER_BARS | `65659d06b5ca0667ef2bb2e4` | `Metric` | `Bar Color` (required) |
| BUBBLES | `65659d06b5ca0667ef2bb2e2` | `Bubble Size` | `Bubble Color` |
| PIE | `65659d06b5ca0667ef2bb2e8` | `Size` | from `Group By` colours |
| DONUT | `65659d06b5ca0667ef2bb2f2` | `Size` | from `Group By` colours |
| KPI | `65659d06b5ca0667ef2bb2f4` | `Metric` | `Conditional Formatting` |
| RAW_DATA_TABLE | `65659d06b5ca0667ef2bb2ea` | `Columns` | none |
| PIVOT_TABLE | `65659d06b5ca0667ef2bb2e9` | `Metrics` | `Conditional Formatting` |
| FLOATING_BUBBLES | `65659d06b5ca0667ef2bb2f6` | `Size` plus `Y Axis` | from `Group By` colours |
| HEAT_MAP | `65659d06b5ca0667ef2bb2ef` | none | `Color Metric` |
| LINE_CHART | `65659d06b5ca0667ef2bb2e6` | `Metric` | from `Group By` colours |
| COMBO_CHART | `65659d06b5ca0667ef2bb341` | `Metric` | varies |
| TREE_MAP | `65659d06b5ca0667ef2bb2ee` | `Size` | `Color Metric` |
| WORD_CLOUD | `65659d06b5ca0667ef2bb2e7` | `Size` | from `Group By` colours |

**These IDs are instance-specific.** Peter captured them against the UAT box
`uat.logi-symphony.com`, and states plainly that other Composer instances issue
different IDs (`Composer-Visual-Types-Guide.md:684`). Treat the table as a shape
reference and a fallback, and resolve the live values with
`composer_get_source_visual_types(source_id=...)` or
`GET /api/visual-types` before writing to an unfamiliar instance. Note the
shared prefix `65659d06b5ca0667ef2bb2` across twelve of the thirteen rows: these
are Mongo ObjectIds minted in one seeding pass, so a differently seeded instance
will diverge wholesale rather than row by row.

## The create envelope

`POST /api/visuals` (`Composer-Visual-Types-Guide.md:11-40`):

```json
{
  "visualTypeId": "<hex ID>",
  "type": "<type string>",
  "visualName": "My Visual",
  "source": {
    "sourceId": "<data source ID>",
    "sourceName": "<data source name>",
    "variables": { },
    "filters": [],
    "aggregateFilters": [],
    "playbackMode": false,
    "live": false,
    "textSearchEnabled": false
  },
  "controlsCfg": {
    "timeControlCfg": {
      "from": "+$start_of_data",
      "to": "+$end_of_data",
      "timeField": "<time field name>"
    },
    "sharpeningCfg": { "prefer": false, "maxQueries": 10 }
  }
}
```

Peter's rule at `:42`: default `timeControlCfg` to the full dataset range
(`+$start_of_data` to `+$end_of_data`) unless a narrower range was asked for,
and include the block at all only when the source has a TIME field.

## Per-type configuration shapes

### UBER_BARS

`Composer-Visual-Types-Guide.md:46-128`. Buckets are `Multi Group By`, `Metric`,
`Bar Color`, plus two settings objects that `SCHEMA_NOTES.md` does not cover.

`UberBarsSettings` (`:93-104`, options enumerated at `:124-128`):

```json
{
  "chartType": "normal",
  "chartOrientation": "vertical",
  "thickness": 100,
  "showAbsoluteValues": true,
  "showRelativeValues": false,
  "showGroupLabels": false,
  "horizontalScroll": false,
  "verticalScroll": false,
  "labelsPosition": "outside",
  "labelsRotate": 0
}
```

`chartType` accepts `normal`, `stacked`, `100_stacked`. `chartOrientation`
accepts `vertical`, `horizontal`. `labelsPosition` accepts `outside`, `inside`.

`Rulers` (`:105-119`) carries gridlines, axes and reference lines:

```json
{
  "gridlines": { "X1grid": true, "Y1grid": false, "X2grid": false, "Y2grid": false },
  "axis": [
    { "name": "Metric", "axis": "Metric", "fromAuto": true, "toAuto": true,
      "stepAuto": true, "logScaleEnabled": false, "metricsName": "Total Revenue Eur" }
  ],
  "reflines": []
}
```

`reflines` here is worth noting against the entry in `SCHEMA_NOTES.md` under
"Things you cannot do via the v25 API", which records that reference lines do
not round-trip on LINE_AND_BARS because that type has no reference-line
variable. UBER_BARS has the slot. Whether a populated `reflines` array survives
a write on UBER_BARS is untested by Peter and untested here; his example ships
it empty.

A `Multi Group By` entry (`:66-86`) carries its own sort, limit and colour
block: `limit`, `sort` (`{name, dir, label, type, metricFunc}`), `type`,
`label`, `includeBlanks`, `groupColorSet`, `autoShowColorLegend`, `colorNumb`,
`autoColor`, `groupColors`.

### BUBBLES

`:132-188`. Buckets: `Group By` (object), `Bubble Size` (array),
`Bubble Color` (array), `Formatting`. `Bubble Color` entries need a
`colorConfig` block (`:176-184`):

```json
{ "colorNumb": 3, "legendType": "palette", "colorSet": "_inherit",
  "autoShowColorLegend": true, "separateNegativeColor": false,
  "autoColor": true, "colorScaleType": "gradient" }
```

### DONUT and PIE

`:193-249`. Buckets: `Group By` (object), `Size` (array), `UberBarsSettings`,
`Formatting`. On these two types `UberBarsSettings` is cut down to label
display only: `showAbsoluteValues`, `showRelativeValues`, `showGroupLabels`
(`:233-237`). PIE takes the same variable structure as DONUT and differs only in
rendering (`:249`).

### KPI

Bucket list and the working no-comparison example are at `:253-364`. Two shapes
that will break a KPI if you get them wrong (`:263-264`):

* `Comparison Metric` must be `[{"name": "none"}]` when there is no comparison.
  An empty array causes rendering errors.
* `Comparison.mode` must be `"off"` in the same case. `"value"` without a valid
  comparison metric throws JavaScript errors in the client.

The colour variables (`Label Color`, `Metric Color`, `Up Arrow Color`,
`Down Arrow Color`) take `"_inherit"` to follow the theme, and
`Metrics Labels` keys the display label by field name concatenated with the
aggregate, for example `"total_revenue_eursum"` (`:339-345`).

**KPI conditional formatting is documented elsewhere and not repeated here.**
The dark-tile trap, that `Background Color` alone will not override a dark theme
and Conditional Formatting rules are required instead, is in Peter's guide at
`:263` (bucket table row) with the worked ruleset at `:278-310`, and the fuller
rule grammar (condition types, `namedTargets` values, `single` versus `palette`
formats, rule ordering) is in his
`logi-composer-toolkit/mcp-server/CLAUDE.md:155-230`. Amin already holds the
trap and the fix in `~/composer-mcp/THEMES.md` under "KPI conditional formatting
(the dark-tile trap)", lines 134 to 152, alongside the four KPI palettes. Read
that; the MCP wraps the write as `composer_set_kpi_conditional_format`.

### RAW_DATA_TABLE

`:424-465`. Buckets: `Columns`, `Grouped Columns`, `Metrics`, `Rows per Fetch`,
`ChartSettings`, `Columns Sort`, `Column State`, `Conditional Formatting`,
`Formatting`, and an `InteractivityState` of `{"profile": {}}`. `Columns`
entries are `{name, label, type}` where type is `ATTRIBUTE` or `NUMBER`.
`ChartSettings` is `{"pagination": {"mode": "pagination"}, "distinct": true}`.

### PIVOT_TABLE

`:470-529`. Beyond the three buckets already in `SCHEMA_NOTES.md`, Peter records
the scale controls and the settings object. `Metric Direction` is `"Columns"` or
`"Rows"`. The limits in his working example are `Column Limit` 4000,
`Rows per Page` 200, `Cell Limit` 1000000 (`:506-508`); he does not say whether
these are ceilings enforced by Composer or simply the values he used, so treat
them as known-good rather than as documented maxima. `ChartSettings` splits into
`columns` (`freezeRows`, `freezeTotals`, `showTotalsColumn`,
`groupRepeatingRows`, `showRollupLabels`), `rows` (`showTotalsRow`), `metrics`
(`showSubtotal`) and a top-level `expanded` of `-1`. Four separate sort arrays
exist: `Row Sorting`, `Column Sorting`, `Metric Sorting`, `Total Sorting`. TIME
fields in `Row Attributes` need an explicit granularity `func`, for example
`"func": "MONTH"` (`:479`).

### FLOATING_BUBBLES

`:534-579`. Buckets: `Multi Group By` (array), `Size`, `Y Axis`, `Formatting`.
This is the type that needs two metric buckets filled to plot anything.

### HEAT_MAP

`:584-649`. Buckets: `Multi Group By` with exactly two dimensions, one for rows
and one for columns; `Color Metric` carrying a `colorConfig`; and both
`Show Metric Values` (boolean) and `ShowMetricValues` (`{"show": true}`). The
duplicated key in two spellings is Peter's, from a payload he had working. He
does not say which one Composer actually reads, so send both.

## Traps

Peter's list is at `:672-684`. Restating the ones that are not already in
`SCHEMA_NOTES.md`:

1. **`Group By` is an object on BUBBLES, DONUT and PIE**, while most other types
   use `Multi Group By` as an array. Passing an array to `Group By` on these
   types fails (`:676`).
2. **Colour buckets need `colorConfig`.** `Bubble Color` and the heat map's
   `Color Metric` need the palette block or the colour legend may not render
   (`:678`).
3. **`_inherit` versus a named colour set.** `"_inherit"` follows the dashboard
   or theme palette; `"DefaultSequential"` and `"DefaultQualitative"` pin an
   explicit one (`:680`).
4. **`timeControlCfg` only when the source has a TIME field** (`:682`).

On UBER_BARS `Bar Color`, Peter and Amin's existing notes agree on the rule and
report different symptoms: Peter has omitting it producing "You do not have
access to view all of the data in this visual" against the Color slot (`:674`),
while `SCHEMA_NOTES.md` has setting it to `[]` returning HTTP 200 and then
breaking at render time. Both point the same way, so set `Bar Color` to the same
metric as `Metric` and move on.

## Provenance and reliability

Everything above comes from Peter's hand-written guide. His generated REST
reference in the same bundle has unreliable metadata (endpoint summaries that
read only "OK", and `GET /api/actions/{id}` filed under `accounts`), so where
the two disagree the hand-written guide wins. Nothing in this file was
contradicted by the generated reference, because nothing here was taken from it.

No claim in this file has been re-verified against a live Composer instance by
Amin. The visual type IDs in particular are Peter's UAT values as of the
2026-05-21 bundle.
