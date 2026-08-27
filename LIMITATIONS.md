# What you can't do via the Composer v25 API

Single canonical list of things this MCP **does not** wrap, with the reason
and (where one exists) the workaround. Every entry below has been verified
empirically against a Composer instance during a cross-warehouse build.

When debugging "why is this 403/404/500?", check here before assuming you've
got a code bug.

## Hard limits (gated by role — needs Symphony global admin)

These return 403 from a tenant-admin session even on resources that tenant
owns. The MCP captures the read side of each but cannot wrap the write
side from a tenant-admin context.

### Trusted Access client registration
* **Endpoint:** `POST /api/trusted-access/clients`
* **Symptom:** `403 Forbidden / Access Denied` from a tenant-admin session.
* **What this blocks:** You can't register the embed client yourself.
  Without a registered + scoped client, `composer_mint_push_token` returns
  `500 can't get authentication`.
* **Workaround:** Ask Symphony global admin (or insightsoftware ops) to
  register the client and scope it to the target account, then they hand
  you the `clientId` + `secret`. Use `composer_verify_trusted_access_client`
  to confirm the registration before you start debugging anything else.

### Theme content writes
* **Endpoint:** `PUT /api/customization/themes/{id}` and `POST /api/customization/themes`
* **Symptom:** `403 Forbidden / Access Denied`, even on themes the tenant
  created via the UI.
* **What this blocks:** You can't recolour the chart palette server-side
  for embeds. So if you want all UBER_BARS bars in your brand red, the
  theme path is closed to you.
* **Workaround three ways out:**
  1. Pass `theme: '__platform__'` to the embed manager so per-visual
     palette settings win (see `composer_set_uber_bars_palette`).
  2. Apply branding via shell CSS — Composer renders native DOM, your CSS
     reaches in. See `EMBEDDING.md` for the canonical override block.
  3. Ask Symphony global admin to make the theme edits.

### Account / tenant enumeration
* **Endpoint:** `GET /api/accounts`
* **Symptom:** `403 Forbidden` for non-global-admin users.
* **What this blocks:** Tenant admins can switch into a tenant they own
  (`composer_switch_tenant`) but can't list every tenant on the instance.
* **Workaround:** Use `composer_whoami` — it returns `accountsVisible`
  count which tells you whether you have global vs tenant scope.

## Server bugs that look like API problems

Verified empirically on 2026-05-07/08 against UAT v25. Each one ate
hours before we found the workaround.

### Source-level Row Security 500s on cross-warehouse joined sources
* **Endpoint:** `POST /api/sources/{id}/fields/{field}/statistics/total`
  (called automatically by the data engine pre-flight when any visual
  renders under a row-security rule)
* **Symptom:** Every widget on the dashboard renders "Error while
  preparing the request. Please contact system administrator."
  Network shows `{"error":"Internal Server Error", "details":"Can't
  get field statistics, service response code: 500"}` for the
  field-stats endpoint.
* **Trigger:** Source-level Row Security rule with
  `<col> INCLUDE ${User.<attr>}` (or any operator) when `<col>` exists
  in only one of the joined entities of a cross-warehouse source.
  A Snowflake `Partners` ⋈ BigQuery `Article Attributes` joined
  source hits this every time. Repro reduced from the rule alone with
  a TEXT column; doesn't require interpolation to fail.
* **Workaround:** Don't apply the rule on cross-warehouse sources at
  the column level. Use per-visual `source.filters` PUT (singular
  `value` key) instead. `embed/serve_nocache.py` ships a working
  `/api/persona` proxy that bulk-PUTs all dashboard widgets per
  persona. See the "Forced filters (row-level security)" section in
  `SCHEMA_NOTES.md` for the full pattern.

### TA_PUSH-only users cannot drive the data engine
* **Symptom:** Embed renders chrome, visual configs fetch (200 OK),
  permissions endpoints return identical results to a working user,
  but no query ever fires. Spinners forever.
* **Trigger:** Mint a push token for a user whose `userOrigin` is
  `TA_PUSH` and who has no MDR-side counterpart. Reproduced against
  `ta.embed` and `demo.admin` even after granting them the
  full role bag (Administrators / Supervisors / Content Distributors
  → 32 roles) and READ + DATA_ACCESS at user and account level.
* **Compare:** `admin.synced` (also `userOrigin: TA_PUSH` but MDR-synced
  from a real Symphony Global Administrator account) works on the
  same tokens with the same body shape.
* **Workaround:** Run all embed sessions as one MDR-synced user
  underneath. Differentiate personas at the data layer (per-visual
  filter PUT), not at the user layer.
* **Worth raising with engineering:** The data-engine session may
  require an MDR-side user record even when ACL/role checks pass at
  the Discovery side. We never identified the exact gate.

### `dashboard.rowFilters` is accepted but ignored at runtime
* **Symptom:** PUT `/api/dashboards/{id}` with `rowFilters: [{sourceId,
  path: "<col>", operation: "IN", value: [...]}]` returns 200, the
  filter persists on read-back, but the engine renders full data.
* **The shape Composer accepts is `value` (singular)** — `values`
  (plural) errors with "Non-composite filters must assign value to
  multiple fields with values=[null]". Singular `value` accepts a
  string OR an array of strings; both store as an array. But neither
  actually filters anything.
* **Workaround:** Use `visual.source.filters` (per-widget) instead.
  Same `value` singular-key shape, but applied at the visual level it
  actually filters at runtime.

### `embed.js createComponent({filters})` is the filter pane, not the data
* **Symptom:** Pass `filters: [{path, operation, values}]` to
  `createComponent('dashboard', {...})`, expecting per-render row
  filtering. Data doesn't change.
* **Why:** Reading the embed source (`/discovery/embed/embed.js`),
  the `filters` option destructures into
  `this.components.filters = {visible: true}` — it configures filter
  pane visibility, alongside `actions`, `search`, `searchByField`,
  `table`. There's no createComponent option for forced row filters
  on a dashboard component. (The visualization-create route does take
  filters, but that's not what dashboards use.)
* **Workaround:** Bake the filter into `visual.source.filters` via
  REST PUT before re-rendering. Same singular `value` key as above.

### Push token `attributes[].values` is capped at length 1
* **Symptom:** `POST /api/trusted-access/push/tokens` with
  `attributes: [{key: "x", values: ["a","b","c"]}]` returns
  `400 'attributes[0].values' size must be between 0 and 1`.
  Multiple entries with the same key error with `'attributes' should
  not contain duplicates`.
* **Workaround:** Pack a CSV into a single value:
  `values: ["a,b,c"]`. Composer's INCLUDE / IN operator expanding a
  user attribute into a multi-value list relies on the value being a
  CSV string at evaluation time. (Untested at runtime in our
  environment because of the cross-warehouse rule failure above.
  Documented for completeness; if you can use source-level rules in
  your environment, this is the workaround for the API cap.)

## Hard limits (not exposed in this Composer build)

These endpoints don't exist in v25. May land in a future release; not
something role escalation fixes.

### No REST route to a visual's aggregated numbers (SI-bundled chart)
* **Symptom:** `POST /api/export/visualdata/{id}` returns HTTP 500 with
  `"Couldn't get an endpoint for service sdk-service"`. So do
  `/api/export/rawdataforvisual` and the rest of the `/api/export/*`
  family.
* **Cause:** the SI chart ships no `sdk-service`. Verified 27 Aug 2026 on
  three separate 26.2.1 rigs: none of them lists it in
  `kubectl -n simba-intel get svc`. This is a packaging gap, not a
  permissions or licence problem, and it is identical on every rig, so
  moving instances does not help.
* **Also not a way round it:** `GET /api/sources/{id}/data` does exist and
  is marked experimental in the live OpenAPI at `/discovery/api-docs`, but
  it returns raw rows only. No aggregation, no custom metrics.
* **Workaround:** the query path in this deployment shape is the
  WebSocket. To read a metric's computed value, render it (an embedded
  dashboard works) and read the value from the DOM, or read the generated
  SQL from the `discovery-query-engine` pod logs and run it yourself.
  Note that Composer computes custom-metric arithmetic **above** SQL, so
  the SQL alone will not give you the metric, only its components.

### Trusted Access is licence-gated, the metadata API is not
* **Symptom:** Basic-auth CRUD against `/discovery/api` keeps working
  normally, while `POST /api/trusted-access/pull/tokens` returns 401
  `"User authentication has been denied. The license to Logi Composer has
  expired."`
* **Why it misleads:** the instance looks healthy from every scripted
  check that only touches metadata. Embedding is the first thing to fail
  and it fails as an auth error, not a licence error, so the obvious
  suspects are the client id and secret.
* **Check first:** `GET /api/license` reports `expired` and
  `expirationDate` in plain fields. Apply a valid key with
  `POST /api/license` and `{"licenseKey": "..."}`.

### Reference lines on LINE_AND_BARS
* **What you'd try:** Adding a horizontal target line at ROAS = 2.5 on the
  trend chart so viewers can see "are we above target?" at a glance.
* **Why it doesn't work:** `LINE_AND_BARS.source.variables` keys are
  exactly `Y1 Color, Y1 Axis, Y2 Color, Y2 Axis, Formatting, Trend Attribute`.
  No reference-line variable. The UI lets you draw them; the API does not
  round-trip them.
* **Workaround:** None via API. Either lean on conditional formatting at
  the cell level (`composer_set_kpi_conditional_format`) for KPI tiles,
  or accept that reference lines need to be drawn manually in the UI per
  dashboard and won't survive cross-tenant migration.

### Saved views / bookmarks
* **What you'd try:** A "save my filter selection" personalisation per
  user so the partner returns to their last view.
* **Why it doesn't work:** All six candidate endpoints return 404 in v25:
  `/dashboards/{id}/views`, `/dashboards/{id}/bookmarks`,
  `/dashboards/{id}/states`, `/dashboards/{id}/personalizations`,
  `/views?dashboardId=`, `/bookmarks?dashboardId=`. Not exposed in this
  build.
* **Workaround:** None via API. If your embed shell needs persistent
  filter state per user, store it client-side (localStorage scoped to
  the username) and restore on page load by setting filter widgets via
  the embed manager's filter API.

### Visual sharing across dashboards
* **What you'd try:** Reuse one KPI visual on three different dashboards
  to keep the metric definition single-source-of-truth.
* **Why it doesn't work:** Composer rejects with "visuals already used in
  other dashboards". Each visual can belong to exactly one dashboard.
* **Workaround:** Use the TOP/IN_DASHBOARD pairing pattern
  (`composer_create_visual_pair`). The TOP twin lives in the Visual
  Gallery; clone it with `composer_clone_for_dashboard` per consumer
  dashboard. Lineage is implicit (same `visId`), not enforced.

## Embed manager limits

These are properties of the `embed.js` runtime, not of the REST API. No API
call would fix them.

### Theme override beats per-visual palette
* **Symptom:** You set `Bar Color` on a UBER_BARS visual to the brand
  colour, the visual renders in that colour in Composer's standalone view,
  but the embed shows the default rainbow palette.
* **Why:** When `createComponent({theme: '<custom>'})` is passed, the
  named theme's `customProperties.charts.*` palette overrides per-visual
  palette at render time.
* **Workaround:** Pass `theme: '__platform__'` (or omit) and apply
  branding via shell CSS overrides documented in `EMBEDDING.md`.

### Visual config cache against the push-token session
* **Symptom:** You edit a visual via the API, the change is persisted
  (verified by re-fetching), but the embedded dashboard still shows the
  old version until you reload the page.
* **Why:** The embed manager fetches visual configs at `createComponent`
  time and caches them for the session.
* **Workaround:** Reload the page (which mints a fresh push token and
  re-fetches everything). For development, make sure your dev server
  sends `Cache-Control: no-store` so the shell HTML itself isn't cached
  too — see `embed/serve_nocache.py`.

### Cross-tab filter state isolation
* **Symptom:** Selecting "Awareness" on the Campaign Type filter in one
  embedded dashboard does not propagate to another dashboard embedded in
  the same shell.
* **Why:** Each `createComponent` returns an independent component
  instance with its own filter state. The embed manager doesn't ship a
  cross-instance state bridge.
* **Workaround:** Listen for filter-change events on each component via
  the embed manager's event API and propagate manually to the others.
  The MCP doesn't wrap this because the wiring lives in your shell JS.

### `display: none` zero-height widget bug
* **Symptom:** Widgets render at zero height when their pane is initially
  hidden. Pivot tables in particular show only column headers, no rows.
* **Why:** The embed measures host element dimensions ONCE at render time.
  If the host is `display: none`, the measurement is zero.
* **Workaround:** In a tabbed shell, swap panes via `opacity` + `z-index`
  + `pointer-events`, never `display: none`. After tab switch, dispatch a
  synthetic `resize` event to wake any deferred render paths. See
  `EMBEDDING.md` for the canonical pattern.

## Open embed issues tracked in Jira

Live Composer embed defects (not API limits, not shell bugs) confirmed in Jira
as of 2026-05-21. Check the ticket for current status before you spend time
debugging; the workaround is what was known at the time.

### Double-click on Save / Save as can create duplicate reports
* **Ticket:** ZP-28872 (Composer v25.4.2)
* **Symptom:** Clicking Save as on an embedded dashboard (not inside the
  Composer web app) and double-clicking the button can create duplicate reports.
* **Workaround:** Debounce or disable your own Save / Save-as control after the
  first click in the embed shell.

### Visual Builder embed breaks when a sourceId is passed
* **Ticket:** ZP-28728
* **Symptom:** The visual-builder embed component breaks when a `sourceId` is
  passed alongside `interactivityOverrides`.
* **Note:** Use the nested `interactivityOverrides` schema (`settings` /
  `visualSettings`), not the flat map. See `EMBEDDING_RUNTIME.md`.

### OR filters do not apply as initialFilters
* **Ticket:** ZP-28398
* **Symptom:** `initialFilters` with an OR `applyFiltersStrategy` passed to
  `embedManager.createComponent` does not filter as expected.
* **Workaround:** Apply the filter at the data layer (per-visual
  `source.filters`) or via the runtime publish methods in
  `EMBEDDING_RUNTIME.md`.

### logi-embed npm package is missing token refresh
* **Ticket:** ZP-28831
* **Symptom:** The `logi-embed` npm package does not include the token-refresh
  behaviour that `window.initComposerEmbedManager` provides, so TypeScript
  integrations using the package lose silent re-auth.
* **Workaround:** Wire your own `getToken` refresh, or use the script-tag
  `window.initComposerEmbedManager` path until the package reaches parity.

### WebSocket console warnings on embedded reports
* **Ticket:** ZP-28487
* **Symptom:** WebSocket warning and error messages appear in the browser
  console on embedded reports; reproducible on the public playground too.
* **Note:** Cosmetic in the cases observed; it does not block rendering. Don't
  chase it as your own bug.

## Schema gotchas (works, but only if you know the trick)

These DO work via the MCP — they're documented here so you know to use the
helper rather than reinventing.

| Gotcha | The trap | The MCP helper |
|---|---|---|
| `Bar Color.colors` shape | Bare hex strings 400 | `composer_set_uber_bars_palette` wraps `{name, color}` |
| Push token `account` field | Slug fails, only display name works | `mint_push_token` docstring + `verify_trusted_access_client` diagnostic |
| Dashboard layout source of truth | `widget.layout` is vestigial | `composer_resize_widget_in_layout` writes `dashboardLayout.layout` |
| BigQuery OAuth client type | Desktop hangs, only Web works | `composer_create_bigquery_oauth_connection` docstring flags it |
| Multi-entity field uniqueness | Collisions silently fall back to default content | `composer_validate_source_field_uniqueness` |
| `unifiedBarCfgs` on dashboard create | Triggers HV000028 Hibernate validation | `composer_create_dashboard` docs say add via PUT after create |
| Expression `NULLIF` | Not supported, divisions silently 0 | `sources.safe_div_expression` builds the CASE WHEN guard |
| `PERCENTAGE` numberFormat | Rejects `standardUnit` | `sources.NUMBER_FORMATS["PERCENT"]` preset |
| API-created tenants invisible in UI | UI filter excludes ObjectId-format ids | Create via UI for admin-list visibility, or use API for headless setups |
| Bundled Symphony mutations 403 | "Session expired" message is misleading | Client adds `X-CSRF-TOKEN` automatically when `COMPOSER_CSRF_TOKEN` is set |
| Per-visual `source.filters` value shape | `values` (plural) silently strips, stores `path: null` | Use `value` (singular) — accepts string or array, persists and filters at runtime |
| Per-persona row narrowing | Source-RLS 500s on cross-warehouse joined sources; `dashboard.rowFilters` ignored; `createComponent({filters})` is UI not data | `embed/serve_nocache.py`'s `/api/persona` proxy bulk-PUTs `visual.source.filters` per widget |

## Where the workarounds live

* `SCHEMA_NOTES.md` — full schema reference per visual type, plus all the
  "off-by-one in a JSON shape" details
* `EMBEDDING.md` — the seven-step embed flow with the shell CSS overrides
  block ready to copy
* `EMBEDDING_RUNTIME.md` — driving the embed after boot: filter passing, event
  capture, modal embeds, interactivity overrides, export interception
* `CHATBOT_EMBED.md` — embedding the Simba Intelligence NLQ chatbot
* `WRITEBACK_ODATA.md` — upload write-back and the OData read API
* `THEMES.md` / `CALCULATIONS.md` / `PYTHON_CONNECTOR.md` — theme JSON, the
  calculation function language, and Python data sources
* `embed/partner-shell.html.template` — the working reference shell
* `embed/serve_nocache.py` — dev server that won't fight your iteration
* This file (`LIMITATIONS.md`) — the "I'm getting an error and want to
  know if it's me or Composer" decision tree
