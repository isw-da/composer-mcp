# Composer v25 schema notes

Every entry below is something we hit at runtime against UAT and had to work
out from error messages or by diffing what the UI sent. Documented so the next
person doesn't burn the same hour.

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
  exist` even when the tenant exists. Confirmed: `'Otto Group'` works,
  `'otto-group'` and the UUID both fail.
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
  (`7d498e0c-c75c-4089-b851-b88875b89432`); tenants created via API have
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
  * `colors`: named palette (`brandColor`, `surface`, `onPrimary`, `text`,
    `intentPrimary`, ...). Other entries reference these as
    `$colors.brandColor`.
  * `customProperties.*`: per-component overrides. The interesting keys for
    dashboards are `customProperties.charts.{KPI, LINE_AND_BARS, UBER_BARS,
    PIVOT_TABLE, ARC, ...}` and `customProperties.colorPalette.colors`.
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
  dedupe.
* `to_native_field()` reshape between describe and create endpoints — the
  `describe` shape includes some fields the `create` endpoint rejects.
* Cross-tenant migration is `GET /api/sources/export?ids=...` then `POST
  /api/sources/import?accountId=<targetTenant>&enableDefaultRead=true`.
  The export preserves encrypted connection passwords across tenants.
* BigQuery schema must be `project.dataset` format, e.g.
  `agile-tracker-403309.otto_demo`.
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
