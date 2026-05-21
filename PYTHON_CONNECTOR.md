# Python as a Composer data source

The Python connector lets an arbitrary Python script act as a data
connection. Each PUBLIC function in the script becomes its own entity/table
that Composer can query, visualise, and embed. The traps below are mostly
about the execution model: it is not a plain `python script.py`, it runs
under JEP inside the Java process and forks per fetch.

## Functions = entities

Every public function definition becomes a separate data source named after
the function. Functions whose names start with `_` are private helpers and
are NOT exposed.

```python
import pandas as pd

def metric_factor_analysis():
    """Public -> becomes a data source called 'metric_factor_analysis'."""
    return pd.DataFrame({"factor": ["A", "B"], "value": [1, 2]})

def _helper():
    """Leading underscore -> NOT a data source."""
    return "internal only"
```

## Supported return types

| Return type | Shape | Notes |
|---|---|---|
| Pandas DataFrame | `pd.DataFrame({...})` | Preferred |
| Dict of lists | `{"col": [v1, v2], ...}` | Key = column, value = column values |
| List of dicts | `[{"col": v}, ...]` | Each dict = one row |
| List of lists | `[[v, v], ...]` | Each inner list = one row |
| List | `[1, 2, 3]` | Single column with index |
| Single value | `1`, `decimal.Decimal("3.14")` | Scalar |

Columns must be uniform: same length, same value type per column, or you get
unexpected behaviour. Type mapping: `str` -> STRING, `int` -> INTEGER,
`float`/`decimal.Decimal` -> DOUBLE, `datetime.date`/`datetime.datetime` ->
DATE, anything else -> STRING. For DataFrames the resolution is via
`dtypes.kind` (e.g. `i`/`u` -> INTEGER, `f` -> DOUBLE, `M` -> DATE,
`O`/`b`/`S`/`U` -> STRING).

## The JEP fork / global-variable trap

This is the one that bites. Two different execution contexts:

- **Validation and describe**: the script is interpreted in the main Java
  process, single thread, shared across ALL users.
- **Fetch data**: the script is interpreted in the main process, then the
  target function runs in a FORKED subprocess.

Consequences:

- Top-level statements run in the main process for all users. Keep the top
  level to imports and function definitions only. No top-level work, no
  shared mutable state.
- Function invocations happen in a separate forked process, so global
  variables defined at the top level are NOT available inside the function.
  Referencing one and reassigning it raises `UnboundLocalError`.
- Each request starts a fresh interpreter. Do not rely on state persisting
  between calls.

```python
# FAILS at runtime:
x = 40
def side_effect():
    x = x + 1          # UnboundLocalError: x referenced before assignment
    return {"result": [x]}

# CORRECT: compute locally, or pass through parameters / a private helper:
def side_effect():
    x = 40
    x = x + 1
    return {"result": [x]}
```

`print()` output (stdout/stderr) is discarded, do not debug with it. If you
need logs, write to a file in one of the writable directories.

### Reserved names and pre-imports

Do not override the connector's internal names: `__convert`,
`__convert_list_of_dicts_to_dict_of_lists`, `f`, `__fork`, `__emulate`,
`all_functions`. Do not shadow the pre-imported modules: `pandas`,
`numbers`, `datetime`, `multiprocessing`, `queue`, `inspect`, `types`.

## Writable directories

The container runs as a non-root user with limited filesystem access. Writes
(logs, temp files, cached data) only succeed in:

- `/opt/zoomdata/logs`
- `/opt/zoomdata/temp`
- `/opt/zoomdata/lib`
- `/opt/zoomdata/wrappers`

## Feature support

Raw data mode only, no pushdown of aggregations: Composer aggregates
client-side, so minimise the rows you return (filter server-side first).
Available as a Docker image, so Docker must be installed on the connector
host.

| Feature | Supported |
|---|---|
| Custom SQL Queries | Yes |
| Derived Fields (row-level expressions) | Yes |
| Distinct Counts | Yes |
| Group By Multiple Fields | Yes |
| Group By Time / UNIX Time | Yes |
| Histograms (incl. floating point) | Yes |
| Last Value | Yes |
| Wildcard Filters (case-sensitive / insensitive) | Yes |
| Box Plots | Yes |
| Admin-Defined Functions | No |
| Fast Distinct Values | No |
| Kerberos Authentication | No |
| Live Mode and Playback | No |
| Multivalued Fields | No |
| Nested Fields | No |
| Partitions | No |
| Pushdown Joins for Fusion Data Sources | No |
| Schemas | No |
| Text Search | No |
| TLS | No |
| User Delegation | No |

## Minimal connector skeleton

Generic shape: one public entity backed by a private fetch helper, plus a
private compute helper. Replace the placeholder columns and the fetch with
your own. Note that all configuration is read inside the helper (not at the
top level) to respect the fork model, and the data fetch is rate-limited to
what the visual needs.

```python
import pandas as pd

# Config lives inside helpers, NOT at module top level (fork model).
def _config():
    return {
        "api_base": "https://<data-host>/rest/v1",
        "api_key": "<api-key>",          # inject via a secret, not hardcoded
        "table": "<view-name>",
    }

def _fetch():
    """Private: pull raw rows. Filter server-side to keep the result small."""
    import urllib.request
    import json
    cfg = _config()
    url = f"{cfg['api_base']}/{cfg['table']}?select=*&limit=10000"
    req = urllib.request.Request(url)
    req.add_header("apikey", cfg["api_key"])
    req.add_header("Authorization", f"Bearer {cfg['api_key']}")
    with urllib.request.urlopen(req) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    df = pd.DataFrame(rows)
    for col in ["metric_value", "baseline_value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df

def _factor_breakdown(df):
    """Private: per-factor deviation from the group baseline, with a flag."""
    out = []
    for group_id, g in df.groupby("group_id"):
        baseline = g["metric_value"].mean()
        for factor, fg in g.groupby("factor"):
            value = fg["metric_value"].mean()
            deviation = round(value - baseline, 2)
            out.append({
                "group_id": group_id,
                "factor": str(factor),
                "metric_value": round(value, 2),
                "baseline_value": round(baseline, 2),
                "deviation": deviation,
                "performance": (
                    "Above" if deviation > 0
                    else "Below" if deviation < 0
                    else "On target"
                ),
            })
    return pd.DataFrame(out)

def factor_analysis():
    """Public entity: one row per factor per group, with deviation flags."""
    return _factor_breakdown(_fetch())
```

### Review checklist

1. All entity functions are public; helpers start with `_`.
2. Top level holds only imports and `def`s, no work, no shared state.
3. No global variables referenced inside functions.
4. No reserved names overridden, no pre-imported modules shadowed.
5. Uniform column lengths and consistent types per column.
6. No `print()` debugging; write to a writable directory if you need logs.
7. File writes only to `/opt/zoomdata/{logs,temp,lib,wrappers}`.
8. `datetime.date` / `datetime.datetime` for date columns, not strings.
9. Row volume minimised; no pushdown aggregation to lean on.

## Sources

Presented from the empirical Composer Python connector guide in the toolkit:
the function-as-entity model, the return-type and type-conversion tables,
the JEP fork / global-variable trap, the writable directories, and the
feature-support matrix. The skeleton is a generic factor-analysis example
written for this file, not a customer script. No fabricated official URLs.
