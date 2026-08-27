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

Peter records all three as required (`:38`, `:205`). Live on 26.2.0, `dataType` is
optional and defaults to `"NUMBER"` when omitted. See "Settled live" below.

The other verbs (`:61-67`): `GET` and `DELETE` on the same per-name path, and
`PATCH` on it for visibility only.

## Limits Peter records

* ~~**Extra body fields are rejected.**~~ Peter records that sending `format`,
  `numberFormat` or `visible` returns HTTP 400 and that Composer sets those itself
  (`:40`, `:204`). **Tested false on 26.2.0, 27 August 2026.** Both fields are
  accepted on both verbs and both are applied, not defaulted over. See "Settled
  live" below.
* **`sourceId` format.** Maximum 36 characters, lowercase letters, digits and
  dashes only, no underscores, and it may not start or end with a dash (`:203`).
* **Field references use the field `name`, never the label** (`:71`, `:206`):
  `ad_spend_eur`, not `Ad Spend Eur`.
* **Naming convention.** `customMetricName` in snake_case for the path,
  `label` in title case for display (`:196-197`).
* ~~**Division by zero returns null**~~ and Composer renders that without erroring
  (`:90`). **Tested false on 26.2.0, 27 August 2026.** It returns `Infinity`, and
  the KPI renders that word. See "Settled live" below.

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

### Settled live on Composer 26.2.0, 27 August 2026

Both shapes were run against a throwaway source on a live 26.2.0 instance. Method
and raw results: [`_run/LIVE-TEST-20260827.md`](_run/LIVE-TEST-20260827.md).

**Neither party was wrong about their own endpoint. Both work.** Peter's `PUT` to
the per-name path and Amin's `POST` to the collection both return 201 and store an
identical resource. What was wrong is the claim that the other side's fields are
rejected.

Seven body variants all returned 201, including the two Peter documents as 400
(`numberFormat` in the body, and `visible` in the body). Beyond acceptance:

* **`numberFormat` is applied.** A deliberately distinctive
  `CURRENCY`/`GBP`/`decimals 4` round-tripped exactly, on both verbs. So the
  `sources.NUMBER_FORMATS` presets do real work and need no follow-up `PATCH`.
* **`visible: false` is applied** and reads back `false`.
* **`dataType` is optional** and defaults to `"NUMBER"`.
* **`name` is optional on `POST`**; Composer slugifies the label instead.

The distinction that does matter is the verb's semantics, which neither document
carried:

| | `PUT .../custom-metrics/{name}` | `POST .../custom-metrics` |
|---|---|---|
| New name | 201 | 201 |
| Existing name | 200, updates | 400, `already exists` |
| Update semantics | replaces the whole resource | n/a |

**The trap is `PUT` as an update.** Re-`PUT`ting a metric with a body that omits
`numberFormat` silently reverts the stored format to Composer's default. It is a
full replace, not a merge, which is the same partial-body overwrite `SAFETY.md`
records for `/api/users/{id}`. Use `POST` to create and reach for `PUT` only when
you intend to overwrite every field, or send the full body you read back from `GET`.

`composer_add_custom_metric` needs no change.

### Divide-by-zero: settled, and Peter's answer is the wrong one

Peter says division by zero yields null and Composer copes (`:90`). It does not.
Live on 26.2.0, `sum(a) / (sum(b) - sum(b))` renders the literal string
`Infinity` in a KPI, and its period-over-period comparison renders `NaN`.

The reason is that the arithmetic never reaches SQL. Composer pushes down only the
component aggregates and evaluates the expression above the database, so results
follow IEEE-754 float rules rather than SQL three-valued logic. Nothing returns
null because nothing in the chain is a SQL division.

Peter's second claim, that there is no `CASE WHEN` support, is also false:
`CASE WHEN` validates, stores and evaluates correctly, in upper or lower case, as
does `COALESCE`. `NULLIF` genuinely is unsupported, and rejects at create time with
`Function 'NULLIF' not supported`, so Amin's docstring is right about it.

So `sources.safe_div_expression()` is both supported and load-bearing. The same
dashboard rendered `2.00` for a normal division, `Infinity` for the unguarded
divide-by-zero and `0.00` for the `CASE WHEN` guarded form. Without the wrapper the
number a customer sees is the word "Infinity".
