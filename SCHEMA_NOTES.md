# Composer v25 schema notes

Every entry below is something we hit at runtime against UAT and had to work
out from error messages or by diffing what the UI sent. Documented so the next
person doesn't burn the same hour.

> **Looking for "what can't I do?"** — see `LIMITATIONS.md`. This file is
> the schema reference (shapes, field names, gotchas). LIMITATIONS.md is
> the failure-mode decision tree.

## Authentication

* Standalone Composer (`/composer`) accepts Basic auth on every endpoint.
* Bundled Symphony (`/discovery`) needs a Spring Security session cookie
  (`SESSION`) plus an `X-CSRF-TOKEN` header on every state-changing request.
  Without the CSRF header you get 403 with the misleading message "Your user
  session has expired. Please refresh the page". It is not a session expiry,
  it is the CSRF gate.
* `COMPOSER_BEARER` is a third option, takes precedence over the cookie.

## Trusted Access

* Push token endpoint: `POST /api/trusted-access/push/tokens`. Body shape
  `{username, account, groups, attributes}`. The older `roles` field still
  serialises but is ignored on recent builds; use `groups` for forced-filter
  scoping.
* `account` is the literal tenant display name, **including spaces and case**.
  Probing the slug returns `400 invalid_request: account: <slug> does not
  exist` even when the tenant exists. Confirmed: `'Acme Partners'` works,
  `'acme-partners'` and the UUID both fail.
* Trusted Access *clients* (the clientId+secret in the Basic Auth header)
  must be registered AND scoped to the target account by a Symphony global
  admin. Tenant admins cannot register clients themselves: `POST
  /api/trusted-access/clients` returns 403 from a tenant-admin session.
* Confusingly, `POST /api/trusted-access/push/tokens` ALSO returns 500 if the
  client isn't registered. The error body is "can't get authentication" with
  no further detail. Check client registration first.

## Tenants

* Account list at `GET /api/accounts` (returns 403 unless you have global
  read). Per-tenant admins can switch context but not enumerate.
* `POST /api/accounts` body must be `AccountUserResource` shape:
  `{account: {name, disabled}, users: []}`. Sending `{name}` directly is
  silently accepted but the tenant won't show up in the admin list.
* Tenants created via the UI have UUID-format ids
  (`00000000-0000-4000-8000-000000000000`); tenants created via API have
  ObjectId-format ids. The UI tenant list filters out ObjectId-format ids,
  so API-created tenants are invisible in the admin UI.
* `GET /api/user/switch/{accountId}` switches the active tenant context for
  the current session. All subsequent `/api/*` calls run in that tenant.
  Page reload reverts.

## Themes

* Read at `GET /api/customization/themes/{id}`. NOT `/api/themes/{id}`
  (404).
* Write is gated. PUT/PATCH and POST-create both 403 from a tenant-admin
  session, even on a theme that tenant created. Theme writes need Symphony
  global admin.
* System themes have stable ids: `'modern'`, `'composer'`, `'dark'`,
  `'d+a_light'`, `'__platform__'`. Custom themes are ObjectId.
* Theme content has two halves under `content`:
  * `variables.*`: design tokens. `variables.colors` is the named palette
    (`brandColor`, `surface`, `onPrimary`, `text`, `intentPrimary`, ...);
    other entries reference these as `$colors.brandColor`.
    `variables.palettes` holds the chart palettes, each keyed by series
    count (`DefaultSequential['3'] == ['#084A8A', '#4A88B8', '#C7DAF0']`
    in the Tetra Pak theme). Some older themes put the named palette at
    `content.colors` instead, so readers should try both.
  * `customProperties.*`: per-component overrides. The interesting keys for
    dashboards are `customProperties.charts.{KPI, LINE_AND_BARS, UBER_BARS,
    PIVOT_TABLE, ARC, ...}`. Note `customProperties.colorPalette` styles
    the palette-picker chrome (`background`, `iconColor`, ...) and is not
    the categorical palette — that lives at `variables.palettes`.
* The KPI tile's dark grey strip + cyan value text are
  `charts.KPI."Background Color"` and `charts.KPI."Metric Color"` (default
  `'#585858'` and `$colors.onPrimary` which resolves to `rgb(0, 150, 182)`
  on the modern master theme).

## Dashboards

* `dashboardLayout.layout` is the source of truth for widget positioning.
  Per-widget `layout` (rowSpan/colSpan) is vestigial — Composer reads layout
  entries shaped `{widgetId, path: [row, col], params: [height_pct,
  width_pct]}`. `params` are **percentages of dashboard size**, not grid
  cells.
* Sensible default sizes:
  * KPI tile in a 6-across row: `[14, 16]`
  * LIST_FILTER above content: `[25-30, 100]` (anything <20 squashes the
    options)
  * Full-width trend chart: `[40, 100]`
  * Pivot in a 2-across row: `[30, 50]`
* `unifiedBarCfgs` (the dashboard-level shared time slider) MUST NOT be
  passed on POST — triggers HV000028 Hibernate validation. Add via PUT
  after create.
* `fieldLinks[]` shape: `{label, mappings: [{sourceId, fieldName}]}`.
  Older docs say `{name, fields}` which fails silently.
* Dashboard URL ids use `_` separator (`<accountId>_<dashId>`) but the
  embed manager wants `+` (`<accountId>+<dashId>`).

## Dashboard ACLs

* `PUT /api/dashboards/{id}/acls/bulk` body shape:
  `[{sid: {type, principal}, permission}]`. Common SID types accepted by
  the validator: `'USER'`, `'GROUP'`, `'ACCOUNT'`. The principal field
  is `principal` (or `id`), NOT `name` or `value`.
* Even with the right shape, ACL writes 403 for non-tenant-admin users.
* `GET /api/dashboards/{id}/acls` is more restrictive than the bulk PUT.
  Sometimes you can write but not read.

## Visuals

### Common variable shapes

| Visual type   | Bucket names                                 |
|---------------|----------------------------------------------|
| KPI           | `Metric`, `Comparison Metric`, `Conditional Formatting`, `Formatting` |
| UBER_BARS     | `Multi Group By`, `Metric`, `Bar Color`      |
| LINE_AND_BARS | `Trend Attribute`, `Y Axis`, `Y1 Color`, `Y2 Color`, `Y1 Axis`, `Y2 Axis`, `Formatting` |
| PIVOT_TABLE   | `Row Attributes`, `Column Attributes`, `Metrics` |
| LIST_FILTER   | `Display Value` (two entries: real field + `{name: 'none'}`) |

### Field shape gotchas

* **KPI** `Metric` / `Comparison Metric`: `{name, func}` only. Adding
  `label` is rejected.
* **UBER_BARS** `Multi Group By` sort: `{name, dir, label, type:'METRIC'}`.
  Adding `func` here is rejected even though metric-typed sort needs an
  aggregator. Composer infers it from `Metric`.
* **UBER_BARS** `Bar Color`: must contain a metric entry. Setting it to
  `[]` returns 200 but breaks the visual at render time. Each
  `colorConfig.colors` entry is `{name, color}` — bare hex strings or
  `{color}` alone fail the validator.
* **PIVOT_TABLE** buckets are `Row Attributes` / `Column Attributes` /
  `Metrics` (note the spaces and casing). Wrong names are silently
  accepted on POST but the visual renders default content.
* **LINE_AND_BARS** `Y1 Color` / `Y2 Color` are stored at the variable
  level on the visual, not on the metric. Hex strings.
* **LIST_FILTER** `Display Value` requires the placeholder
  `{name: 'none'}` second entry. Removing it produces a "filter never
  loads" symptom in the rendered widget.

### Less-common visual types

Variable buckets and theme-level chart keys, captured for the types the
MCP doesn't have explicit helpers for. Use `describe_visual_template()` to
verify if a Composer build has shifted these.

| Visual type   | Variable buckets                              | Theme keys                              |
|---------------|-----------------------------------------------|-----------------------------------------|
| ARC           | `Metric`, `Group By`                          | `Label Color`, `Label Description Color` |
| BULLET_GAUGE  | `Metric`, `Target`, `Comparison Metric`       | `Bar Color`, `Target Color`              |
| COMBO_CHART   | `Trend Attribute`, `Y Axis`, `Y2 Axis`, `Y3 Axis`, `Y4 Axis` | `Y2 Color`, `Y3 Color`, `Y4 Color` |
| HISTOGRAM     | `Metric`, `Bins`, `Cumulative Line`           | `Bins Color`, `Cumulative Line Color`    |

### Things you cannot do via the v25 API

* Reference lines on `LINE_AND_BARS`. The variable list is only `Y1 Color`,
  `Y1 Axis`, `Y2 Color`, `Y2 Axis`, `Formatting`, `Trend Attribute`. No
  reference-line variable. The UI lets you draw them; the API does not
  round-trip them.
* Saved views / bookmarks. All six candidate endpoints
  (`/dashboards/{id}/views`, `/bookmarks`, `/states`,
  `/personalizations`, `/views?dashboardId=`,
  `/bookmarks?dashboardId=`) return 404. Not exposed in v25.
* Editing visuals shared across dashboards. A visual can only belong to
  one dashboard at a time. Use `clone_for_dashboard` to make per-dashboard
  copies.

### Visual / level distinction

Each visual carries a `level`:
* `'TOP'` — appears in the Visual Gallery, browseable standalone.
* `'IN_DASHBOARD'` — scoped to one dashboard widget.

Composer rejects sharing a visual across dashboards. Standard pattern:
build the TOP twin first, then `clone_for_dashboard()` per dashboard.
`create_visual_pair()` does both in one call.

## Sources

* Multi-entity sources need globally unique field names. Composer rejects
  duplicates across entities. Auto-prefix with the entity short name to
  dedupe. Use `validate_source_field_uniqueness()` after edits to catch
  collisions before they cause silent fallback at render time.
* `describe_source_joins()` summarises the join graph and tags the source
  as cross-warehouse if entities span multiple connections.

### Forced filters (row-level security)

Forced filters are appended to every query against a source for sessions
that match the SID. Combine with push-token `groups` or `attributes` for
row-level security:

```
{
  sid: {type: 'GROUP'|'USER'|'ACCOUNT', principal: '<name>'},
  filter: {field: 'partner_id', operator: 'EQUALS'|'IN'|'NOT_EQUALS'|'CONTAINS',
           values: ['<literal>'] OR '${User.<attr>}'},
}
```

`${User.<attr>}` interpolates the attribute the push token carried.
The canonical "everyone sees only their own data" pattern:

```
{sid: {type: 'USER', principal: '*'},
 filter: {field: 'partner_id', operator: 'IN', values: '${User.partner_id}'}}
```

Wrappers in `tools/sources.py`: `list_forced_filters`, `add_forced_filter`,
`remove_forced_filters_for_sid`, `clear_forced_filters`.

**Two failure modes to know about**, both verified live on 2026-05-08
during a cross-warehouse build (Snowflake fact + BigQuery
dim joined in one source). The textbook pattern above silently breaks
when these conditions are met.

#### A. Cross-warehouse joined source breaks the field-stats pre-flight

When the rule's field column lives in only one of the joined entities
(e.g. `partner_name` lives in the Snowflake `Partners` entity, not in
the BigQuery `Article Attributes` entity), every visual that tries to
render under the rule fails with:

```
{"error":"Internal Server Error",
 "details":"Can't get field statistics, service response code: 500"}
```

User sees "Error while preparing the request" on every widget. The
interpolation succeeds (so `${User.persona_partner}` resolves cleanly);
the failure is downstream of that, in the field-stats pre-flight that
Composer runs before query planning.

Fix: don't apply source-level row security on a column that only
exists in one of the joined entities of a cross-warehouse source. If
you need partner-level scoping, either (a) collapse the join into a
single warehouse first, or (b) use the per-visual filter approach
described in (B) below. The MCP can't paper over this — it's a server
bug.

#### B. TA_PUSH-only users can't drive the data engine

Users created purely via push tokens (`userOrigin: TA_PUSH`, no MDR
sync) cannot run queries through the embed even when they hold:

* `READ + DATA_ACCESS` on the source (account level + user level)
* The full role bag (Administrators / Supervisors / Content
  Distributors → 32 roles)
* All required group memberships

Symptom: dashboard chrome renders, visual configs fetch, then no
query ever fires. Spinners forever. The same tokens used by an
MDR-synced user (e.g. `admin.synced` who exists on both sides) work
fine. Verified by minting tokens for `ta.embed` and
`demo.admin` (TA_PUSH only) versus `admin.synced` (MDR-synced)
with identical bodies and identical /api/user/permissions responses
— only the MDR-synced user loaded data.

Fix: run all personas as one MDR-synced user underneath. Differentiate
personas via the data filter, not via swapping users (see C).

#### C. The pattern that does work for per-persona narrowing

When the source-level rule is broken (A) or the embed user can't
change between requests (B), use **per-visual `source.filters` PUT**
across every widget on the dashboard.

The shape that actually filters data at query time is **`value`
(singular key)**, not `values`:

```
[{path: "partner_name",
  operation: "IN",
  value: ["Contoso Ltd", "Fabrikam AG"]}]
```

`values` (plural) is accepted by PUT but Composer strips the array
and stores `path: null` — the filter persists structurally but never
matches anything at runtime. `value` (singular) accepts a single
string OR an array of strings; both store as an array and apply
correctly at runtime.

Per-persona switch flow:

1. Server-side: read every widget visual on the dashboard, set
   `source.filters` to the persona's filter (or `[]` to clear), PUT
   each one back. Strip the `version` and audit fields before PUT.
2. Re-mint the embed token. Re-render the dashboard component (so
   embed.js re-fetches visual configs — see "Visual config cache
   against the push-token session" in `LIMITATIONS.md`).

Working reference: `embed/serve_nocache.py`'s `/api/persona` endpoint
ships this proxy. The partner shell calls it on persona switch.

#### What does NOT work for per-persona narrowing (don't waste time)

* `dashboard.rowFilters` PUT — accepted, stored, but the engine
  ignores it at render time. Visuals render full data.
* `embed.js createComponent({filters: [...]})` — the `filters`
  option configures the filter PANE visibility, not the data. Read
  `this.components.filters = {visible: true}` in the embed source.
* Push token `attributes[].values` carrying a CSV string — even if
  the rule template auto-splits, you still need the rule to fire,
  and the rule firing on a cross-warehouse source hits failure (A).
  (Also: the push API caps `attributes[].values` at length 1, so
  multi-partner narrowing must encode as a CSV in a single value
  anyway. Documented for completeness, but irrelevant if you take
  the (C) path.)
* `visual.source.filters` with `values` (plural) — values get
  silently stripped, only `path: null` persists. Use `value`
  (singular) per (C) above.

* `to_native_field()` reshape between describe and create endpoints — the
  `describe` shape includes some fields the `create` endpoint rejects.
* Cross-tenant migration is `GET /api/sources/export?ids=...` then `POST
  /api/sources/import?accountId=<targetTenant>&enableDefaultRead=true`.
  The export preserves encrypted connection passwords across tenants.
* BigQuery schema must be `project.dataset` format, e.g.
  `<project>.<dataset>`.
* BigQuery OAuth: web client (not desktop). Desktop clients only allow
  `http://localhost` redirect URIs.

## Reports / PDF subscriptions

* `GET /api/dashboards/{id}/reports` lists scheduled subscriptions.
* Schedule shape:
  ```
  {frequency: DAILY|WEEKLY|MONTHLY,
   dayOfWeek?, dayOfMonth?, timeOfDay,
   startDate, endDate}
  ```
* `POST` to the same path creates one. Most teams configure subscriptions
  via the UI Subscribe dialog because it also wires up email templating
  and consent.
* Recipients are stored on the report record as `[{email: "..."}, ...]`.
  Use `tools.reports.add_report_recipients` / `remove_report_recipients`
  to manage them with PUT-merge semantics rather than reconstructing the
  full record yourself. A subscription created without recipients still
  fires its schedule and produces a PDF — the PDF just goes nowhere.
* `set_report_enabled(False)` pauses a subscription without losing its
  recipient list. Prefer this to `delete` when iterating on schedules.

## Embed Manager (native DOM, no iframe)

See `EMBEDDING.md` for the worked example. Key gotchas:

* The embed manager fetches visual configs at `createComponent` time and
  caches them for the session. Per-visual edits made AFTER the embed
  initialised won't repaint until the page reloads (and the embed
  re-mints its push token).
* `theme: '<name>'` on `createComponent` overrides per-visual palette
  settings. To let visual-level palette edits actually paint, pass
  `theme: '__platform__'` and apply branding via shell CSS.
* Composer's `.zd-main` wrapper uses CSS Grid with a left column for the
  standalone navigation header (`.zd-main-header`, ~900px). In embed mode
  it's empty but still claims its column, squashing the dashboard into
  the right half. Hide it via shell CSS:
  ```
  html body div.zd-main > header.zd-main-header { display: none !important }
  html body div.zd-main > section.zd-main-section { grid-column: 1 / -1 !important }
  ```
* Same trick handles `.zd-custom-header` and `.zd-license-banner` (each
  ~67px of empty top space) and `.logi-embed-main` background gutter
  (`#F7F7F7`).
* Composer's stylesheet loads AFTER the shell `<style>`, so equal-
  specificity rules of the shell lose the cascade. Bump to `html body`
  prefix or inject post-load.
* CSS-module class names (`Tqwvz2y__q2Ib32JOJSD`,
  `W95yvucTZ2S9qC20pz2v`) are stable per Composer build. Targeting them
  via `[class*="Tqwvz2y"]` is safe within a deployment.
