# Composer calculation functions

The expression-function language for Composer calculated fields and derived
metrics. These extend the base aggregates (`sum`, `avg`, `min`, `max`,
`count`, `distinct_count`, `last_value`) with cross-row and cross-group
reach. Three categories: Table, Window, Other.

> **Not the same thing as custom metrics.** This file documents the function
> language. To create the metric that USES these functions (the PUT
> endpoint, the body shape, naming), see `SCHEMA_NOTES.md` and the
> custom-metrics tooling (`composer_add_custom_metric`,
> `composer_list_custom_metrics`, plus `sources.safe_div_expression()` for
> divisions that must not 0 out).

## Table functions

Aggregate across the ENTIRE dataset visible in the current query. They
ignore any grouping on the chart, so they give you the grand total to
compare a grouped value against. They take RAW field names.

| Function | Returns |
|---|---|
| `TableSUM(field)` | Sum across the whole table |
| `TableAVG(field)` | Average across the whole table |
| `TableMIN(field)` | Minimum across the whole table |
| `TableMAX(field)` | Maximum across the whole table |
| `TableCOUNT(field)` | Count across the whole table (all field types) |
| `TableCOUNTD(field)` | Distinct count across the whole table |

## Window functions

Aggregate within a PARTITION defined by an attribute. If the partition
attribute is not on the chart, they behave like Table functions.

| Function | Returns |
|---|---|
| `WindowSUM(metric, attribute)` | Sum of metric within the group |
| `WindowAVG(metric, attribute)` | Average of metric within the group |
| `WindowMIN(metric, attribute)` | Minimum of metric within the group |
| `WindowMAX(metric, attribute)` | Maximum of metric within the group |
| `WindowCOUNT(attribute, group-by attribute)` | Count of records within the group |
| `WindowCOUNTD(attribute, group-by attribute)` | Distinct count within the group |

### The first-argument rule (silent gotcha)

A Window function's first argument MUST be an already-aggregated value, not a
raw field. This is the opposite of Table functions, which take raw fields.
Get it wrong and the expression does not do what you expect.

```
WindowMAX(sum(version), record_id)    correct: first arg is aggregated
WindowMAX(version, record_id)         wrong: version must be aggregated first
```

## Other functions

Date/time manipulation and null handling.

| Function | Returns |
|---|---|
| `NOW()` | Current time |
| `TIME_ADD(period, interval, date)` | Increment/decrement a date. Periods: `YEAR`, `QUARTER`, `MONTH`, `WEEK`, `DAY`, `HOUR`, `MINUTE`, `SECOND`, `MILLISECOND`. Negative interval decrements. |
| `PreviousPeriod(offsetPeriod, numPeriods)` | The previous period relative to the current time filter. Granularity from millisecond up to year. |
| `COALESCE(expr1, expr2, ...)` | First non-NULL expression, or NULL if all are NULL. |

Examples:

```
TIME_ADD('YEAR', 1, '2015-01-01')   -> 2016-01-01
TIME_ADD('DAY', -7, NOW())          -> 7 days ago
TIME_ADD('MONTH', 3, orderDate)     -> order date + 3 months
PreviousPeriod('Months', 5)         -> shift by 5 months
COALESCE(AVG(field), 0)             -> 0 when AVG is NULL
```

## Patterns

### Percent of total

Use a Table function for the grand-total denominator. Returns a 0..1
proportion of each grouped value to the whole:

```
sum(Sales) / TableSUM(Sales)
```

### Percent of category

Use a Window function partitioned by the category for the denominator:

```
sum(Sales) / WindowSUM(sum(Sales), Category)
```

Note the aggregated first argument to `WindowSUM`, per the rule above.

### WindowMAX latest-row de-duplication

When a source appends new versions of a record instead of updating in place
(common with ERP/CRM history tables), Composer sees every version and sums
across all of them, inflating totals. You can de-duplicate to the latest row
entirely in the formula system, no preprocessing.

Structure the data with `record_id`, an incrementing `version` integer, and
the value columns. Then build a latest-row indicator:

```
sum(version) / WindowMAX(sum(version), record_id)
```

This ratio is `1` for the latest version (its version equals the max for
that `record_id`) and `< 1` for older versions. Filter the visual to
rows where the indicator `= 1`, then aggregate the value columns. Worked
example:

| record_id | version | indicator | kept? |
|---|---|---|---|
| ORD-001 | 1 | 1 / 2 = 0.50 | filtered out |
| ORD-001 | 2 | 2 / 2 = 1.00 | kept |
| ORD-002 | 1 | 1 / 1 = 1.00 | kept |

Latest-row-wins, computed in Composer.

## Sources

Presented from the empirical Composer calculations guide in the toolkit:
the three function categories, the Window first-argument rule, the
percent-of-total / percent-of-category patterns, and the WindowMAX
de-duplication trick. No fabricated official URLs.
