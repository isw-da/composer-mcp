# Composer custom metrics: endpoint, body and expression syntax

Absorbed from Peter Armstrong's toolkit, 27 August 2026, source
`~/logi-composer/peter-kb/bundle-2026-05-21/logi-composer-toolkit/docs/Composer-Custom-Metrics-Guide.md`.

## What this file is for

`~/composer-mcp/CALCULATIONS.md` documents the function language (Table
functions, Window functions, the Window first-argument rule, the time and null
helpers) and at lines 8 to 13 deliberately defers the metric object itself:
"To create the metric that USES these functions (the PUT endpoint, the body
shape, naming), see `SCHEMA_NOTES.md` and the custom-metrics tooling". That
pointer was never followed through. This file is the missing half: the endpoint,
the body, the expression grammar around the aggregates, and the limits.

## Custom metric versus calculated field

Peter treats them as the same object: a custom metric is a calculated field
defined on a Composer data source (`Composer-Custom-Metrics-Guide.md:7`). What
matters is where the calculation lives and when it runs. The definition sits on
the source, not on the visual and not in the database, and it is computed at
query time against whatever GROUP BY and filters the visual applies, so one
definition holds at every level of granularity (`:7`). A ratio defined once as
`sum(a) / sum(b)` therefore stays correct when the chart regroups, which a
precomputed column in the warehouse would not.

Every source is given one custom metric for free on creation: **Volume**,
defined as `count(*)` (`:9`). Custom metrics can reference other custom metrics
by internal name (`:9`, `:134-140`).

## Endpoint

Peter's write path (`:14`):

```
PUT /api/sources/{sourceId}/custom-metrics/{customMetricName}
```

Creates or updates, returning HTTP 201 with the stored definition including the
`numberFormat` Composer generated for you (`:42-58`, `:225`).

Required header (`:19`, restated `:202`): `Content-Type:
application/vnd.composer.v3+json`. Plain `application/json` returns 415. Amin's
client already sends the vendor media type on every call
(`~/composer-mcp/src/composer_mcp/client.py:38`), so this is a trap only for raw
curl work.

Body (`:26-38`):

```json
{
  "label": "Conversion Rate",
  "expression": "sum(ad_orders) / sum(clicks)",
  "dataType": "NUMBER"
}
```

All three fields are required. `dataType` is always `"NUMBER"` for a calculated
metric (`:38`, `:205`).

The other verbs (`:61-67`): `GET` and `DELETE` on the same per-name path, and
`PATCH` on it for visibility only.

## Limits Peter records

* **Extra body fields are rejected.** Sending `format`, `numberFormat` or
  `visible` returns HTTP 400; Composer sets those itself (`:40`, `:204`).
* **`sourceId` format.** Maximum 36 characters, lowercase letters, digits and
  dashes only, no underscores, and it may not start or end with a dash (`:203`).
* **Field references use the field `name`, never the label** (`:71`, `:206`):
  `ad_spend_eur`, not `Ad Spend Eur`.
* **Naming convention.** `customMetricName` in snake_case for the path,
  `label` in title case for display (`:196-197`).
* **Division by zero returns null** and Composer renders that without erroring
  (`:90`).

Peter records no cap on the number of custom metrics per source, no expression
length limit, and no restriction on recursion depth when metrics reference other
metrics. Those are unknown rather than unlimited.

## Expression syntax

Expressions apply aggregation functions to source field names (`:71`).

### Aggregates (`:75-84`)

| Function | Returns |
|---|---|
| `sum(field)` | Sum of values |
| `avg(field)` | Average |
| `min(field)` | Minimum |
| `max(field)` | Maximum |
| `count(*)` | Count of all rows |
| `count(field)` | Count of non-null values |
| `distinct_count(field)` | Count of distinct values |
| `last_value(field)` | Last value by time |

These are the same base aggregates `CALCULATIONS.md` names before extending them
with `TableSUM`, `WindowSUM` and the rest. Peter writes them lowercase
throughout; Amin's MCP tool description writes them uppercase (`SUM`, `AVG`).
Neither source states whether the parser is case sensitive, so that is untested.

### Arithmetic (`:86-90`)

`+`, `-`, `*`, `/` between aggregated values.

### WHERE, for filtered aggregation (`:92-106`)

A filter applied inside a single aggregation:

```
sum(revenue) WHERE is_ad_attributed = true
count(*) WHERE campaign_type IN ('Sponsored Product', 'Sponsored Brand')
sum(total_fatal_injuries) WHERE event_year >= 2020
```

Peter shows string literals quoted and bare numeric lists both working
(`:101`, `:131`).

### TRANSFORM, for period comparison (`:108-116`)

Rebases one aggregation onto a different time window:

```
sum(revenue) - (sum(revenue) TRANSFORM order_date = PreviousPeriod())
```

`PreviousPeriod()` is the same helper `CALCULATIONS.md` documents under Other
functions, where it takes `(offsetPeriod, numPeriods)`. Peter calls it with no
arguments here.

### Composition (`:118-140`)

Aggregations, filters and arithmetic combine, and parentheses scope a WHERE to
one operand:

```
(sum(revenue) WHERE is_ad_attributed = true) / sum(ad_spend_eur)
sum(profit) / (sum(sales) WHERE zipcode IN (90210, 94107, 92101))
conversion_rate * 100
```

The last line references an existing custom metric by its internal name.

One of Peter's own examples is worth reading with care. His "percentage of
total" pattern at `:170` is written
`sum(revenue) / sum(revenue) WHERE category = 'Electronics'` without
parentheses, which computes a category share of the total only if WHERE binds to
the right-hand aggregate alone. His other filtered examples parenthesise
explicitly. Parenthesise yours.

For a true percent of total, `CALCULATIONS.md` gives the better construction:
`sum(Sales) / TableSUM(Sales)`, where the Table function ignores the chart's
grouping.

### Worked patterns (`:142-172`, `:208-225`)

Conversion rate `sum(ad_orders) / sum(clicks)`, ROAS
`sum(ad_revenue_eur) / sum(ad_spend_eur)`, yield rate
`sum(good_units) / (sum(good_units) + sum(rejected_units))`, and period change
`sum(revenue) - (sum(revenue) TRANSFORM order_date = PreviousPeriod())`.

## How this maps to Amin's MCP tools

| Peter's call | MCP tool |
|---|---|
| `GET /api/sources/{id}/custom-metrics/{name}` (`:63`) | `composer_list_custom_metrics(source_id)`, which reads the collection rather than one name |
| `PUT /api/sources/{id}/custom-metrics/{name}` (`:14`) | `composer_add_custom_metric(source_id, name, label, expression, number_format=, visible=)` |
| `DELETE /api/sources/{id}/custom-metrics/{name}` (`:65`) | `composer_delete_custom_metric(source_id, name)` |
| `PATCH` for visibility (`:67`) | no wrapper; use the raw client |

Peter's own guide targets a different MCP server and names the tool
`update_source_custom_metrics` (`:175-185`). That name does not exist in Amin's
server; the equivalent is `composer_add_custom_metric`.

### The verb and body disagreement

Peter and Amin's implementation do not match, and this is worth resolving before
the next live run rather than papering over.

* Peter: `PUT` to the per-name path, body of exactly `label`, `expression`,
  `dataType`, and `numberFormat` or `visible` in the body causes a 400
  (`:14`, `:40`, `:204`).
* Amin's MCP: `POST` to the collection path
  (`~/composer-mcp/src/composer_mcp/tools/sources.py`, `add_custom_metric`),
  body of `name`, `label`, `expression`, `visible`, and optionally
  `numberFormat`, with no `dataType` at all.
  `~/composer-mcp/SAFETY.md:187-188` records the same collection-level `GET` and
  `POST`.

Both are empirical, taken against different instances at different times.
Neither has been re-run to settle it. If `add_custom_metric` starts returning
400 on a build where it used to work, Peter's shape is the first thing to try:
drop `visible` and `numberFormat`, add `"dataType": "NUMBER"`, and switch to
`PUT` on the per-name path. The `numberFormat` presets in
`sources.NUMBER_FORMATS` (`EUR`, `USD`, `GBP`, `PERCENT`, `RATIO`, `INTEGER`)
and the quirks they shield you from would then have to be applied by a follow-up
`PATCH` or accepted as Composer's defaults.

### Divide-by-zero: two different answers

Peter says division by zero yields null and Composer copes (`:90`). Amin's MCP
ships `sources.safe_div_expression()`, which wraps the division as
`CASE WHEN denom > 0 THEN num / denom ELSE 0 END` because Composer's expression
language has no `NULLIF`. These give different results, null against zero, and
the choice belongs to whoever reads the chart: null leaves a gap in the series,
zero draws a point at the baseline. Peter documents no `CASE WHEN` support at
all, so a build that matches his shape may reject the safe-division wrapper.
Untested.
