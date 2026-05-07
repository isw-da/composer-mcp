# composer-mcp

MCP server that wraps the Logi Composer v25 REST API as MCP tools.

Built on top of the patterns documented in
[`isw-da/symphony-dashboard-builder-skill`](https://github.com/isw-da/symphony-dashboard-builder-skill).
That skill is a 690-line procedural document; this MCP turns those patterns
into proper tools so any Claude session can drive Composer end-to-end without
re-reading the skill each time.

## What it does

- Connection management (Snowflake, BigQuery, Postgres, etc.) including
  OAuth2 setup for connectors that support it
- Source / field discovery, including the safe `initial-visual` workflow
- **Multi-entity sources with cross-warehouse joins**: helpers for
  introspection, native-field shape conversion, and field-name dedupe
- **Custom (calculated) metrics**: helpers for divide-by-zero-safe
  expressions and ready-made number-format presets
- Visual creation with TOP (Gallery) + IN_DASHBOARD pairing
- Dashboard creation with widget grid layout, field links for filter scoping,
  and per-visual time-window control
- Multi-tenancy: tenant CRUD, user/admin assignment, **session-level tenant
  switching**, dashboard ACL sharing
- **Cross-tenant source migration via export/import** (the only mechanism
  Composer 25 supports for cloning a connection between tenants)
- Trusted access tokens (push for impersonation, pull for SSO)
- **Theme inspection** (`list_themes`, `get_theme`, `describe_theme_palette`).
  Theme writes are gated to Symphony global admin in v25; this MCP covers the
  read side and `EMBEDDING.md` documents the workarounds (per-visual palette
  edits, shell CSS overrides)
- **PDF subscriptions** (`list_dashboard_reports`, `create_dashboard_report`)
- **Layout helpers** (`resize_widget_in_layout`,
  `resize_widgets_by_visual_type`) for fixing widget sizing in
  `dashboardLayout.layout` without re-fetching the full dashboard each time
- **Visual palette helpers**: `set_uber_bars_palette` wraps the gnarly
  `Bar Color.colorConfig.colors` shape (entries must be `{name, color}`,
  not bare strings). `set_kpi_conditional_format` for RedYellowGreen
  thresholding on KPI tiles
- **Embedding reference** (`embed/otto-opc-shell.html.template` plus
  `embed/serve_nocache.py`): a working native-DOM embedding shell with
  hover tooltips, layout overrides, and the dev server config. Worked
  example end-to-end against UAT; see `EMBEDDING.md`
- **Embed orchestration**: `make_embed_config` mints a fresh push token
  and returns the full shell `CONFIG = { ... }` block ready to paste,
  `verify_trusted_access_client` translates the opaque 500 (client not
  registered) and 400 (account out of scope) into actionable diagnostics
- **Row-level security**: `add_forced_filter` / `remove_forced_filters_for_sid`
  for per-group, per-user, or attribute-interpolated forced filters with
  `${User.<attr>}` push-token attribute resolution
- **Cross-warehouse introspection**: `describe_source_joins` summarises
  the join graph and tags sources as cross-warehouse; `validate_source_field_uniqueness`
  catches the silent collision bug that causes Composer to fall back to
  default content
- **Pre-flight render test**: `test_dashboard_render` walks every widget
  and reports per-widget pass/fail by hitting the data preview endpoint.
  Catches placeholder-metric bindings before they embarrass you in front
  of a customer
- **Per-provider connection helpers**: Snowflake, BigQuery (both OAuth
  and Service Account), Postgres, Databricks. Composer's generic
  create_connection works but you have to know each provider's parameter
  shape; these wrap them with the verified-good defaults
- **Diagnostics**: `health_check` sweeps every read-only probe and reports
  which capability classes the calling principal can access plus which
  permission gates apply. `whoami` confirms identity + tenant scope
- **Dashboard templates**: `generate_snapshot_dashboard` produces a
  UC1-style "Today at a glance" dashboard from any source — campaign-type
  filter, KPI tile row with conditional formatting on ROAS, and a
  bar+line trend chart. Skips KPIs whose underlying field is missing
  rather than failing the build

The server enforces the non-negotiable Composer quirks documented in the
skill:

- `application/vnd.composer.v3+json` content type everywhere
- `/composer/api/...` (standalone) or `/discovery/api/...` (SI/Symphony bundle)
- Lists unwrapped from `{content: [...]}` shape
- `level: 'IN_DASHBOARD'` validation on visual creation
- 2-element `path` and `params` arrays in dashboard layouts (Composer v25)
- 32-char hex widget IDs
- **CSRF tokens** added automatically to mutation requests on bundled Symphony

For the long catalogue of v25 schema gotchas we hit (push token `account` is
the literal display name not the slug, `Bar Color.colors` entries need
`{name, color}` shape, `dashboardLayout.layout` is the source of truth not
`widget.layout`, reference lines + saved views aren't exposed in v25, theme
writes 403 for tenant admins, embed manager `theme: '<name>'` overrides
per-visual palette, `.zd-main-header` empty rail squashes embeds, and so on),
see `SCHEMA_NOTES.md`.

## Companion agent

The repo bundles a `bi-developer` subagent definition at
`agents/bi-developer.md` — a Principal BI Developer with a phase-gated
workflow (Frame → Sketch → Build → Verify → Hand-over) that refuses to
write SQL until grain, conformed dimensions, and metric definitions are
explicit. Designed to operate this MCP's tools natively. Install:

```bash
mkdir -p ~/.claude/agents
cp agents/bi-developer.md ~/.claude/agents/
# restart Claude Code
```

Then dispatch via `Agent(subagent_type: "bi-developer", ...)` or say
"use the BI developer agent to...". See `agents/README.md` for project-
scope install, customisation, and tool-pinning options.

## "Why is this 403/404/500?"

When debugging, start at `LIMITATIONS.md`. It's the single canonical list of
what this MCP **does not** wrap, with the failure mode, the root cause, and
the workaround for each. Categorised by:

* **Hard limits gated by role** (Trusted Access client registration, theme
  content writes, account enumeration) — needs Symphony global admin
* **Hard limits not exposed in v25** (reference lines, saved views, visual
  sharing) — needs a future Composer release
* **Embed manager limits** (theme override behaviour, visual config cache,
  cross-tab filter isolation, zero-height widget bug) — properties of
  `embed.js`, no REST API call would fix them
* **Schema gotchas** (works, but only if you know the trick) — table
  cross-referencing each gotcha to the MCP helper that wraps it

## Quick start

```bash
cd ~/composer-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

```bash
COMPOSER_BASE=http://localhost:18080 \
COMPOSER_USER=admin \
COMPOSER_PASSWORD='<your-composer-admin-password>' \
.venv/bin/composer-mcp
```

`COMPOSER_CONTEXT_PATH` defaults to `/composer` (standalone Composer). For
the SI / Symphony bundled deployment, set `COMPOSER_CONTEXT_PATH=/discovery`
and use one of the bundled-Symphony auth modes below.

## Auth modes

Three flavours, in order of preference for unattended scripting.

### 1. Bearer token (recommended)

Stateless. Works on standalone AND bundled. No CSRF.

```bash
COMPOSER_BEARER='<token-from-trusted-access>' .venv/bin/composer-mcp
```

Mint via `composer_mint_pull_token` (existing user) or
`composer_mint_push_token` (impersonation for embedded scenarios).

### 2. Basic auth

Works on standalone Composer. Bundled Symphony usually rejects Basic on the
v3 API.

```bash
COMPOSER_BASE=http://localhost:18080 \
COMPOSER_USER=admin \
COMPOSER_PASSWORD='<password>' \
.venv/bin/composer-mcp
```

### 3. Session cookie + CSRF (bundled Symphony only)

Bundled Symphony is gated by Spring Security CSRF. Read the `SESSION` cookie
value and the `<meta name="_csrf">` content from a logged-in browser tab and
pass both via env vars. Mutations get `X-CSRF-TOKEN` added automatically.

```bash
COMPOSER_BASE=https://uat.logi-symphony.com \
COMPOSER_CONTEXT_PATH=/discovery \
COMPOSER_SESSION_COOKIE='<SESSION cookie value>' \
COMPOSER_CSRF_TOKEN='<_csrf meta value>' \
.venv/bin/composer-mcp
```

Without `COMPOSER_CSRF_TOKEN`, every state-changing request returns 403 with
the misleading "Your user session has expired. Please refresh the page to
get a new user session established before changes can be saved." That's not
a session expiry — it's the CSRF gate.

## Claude Code / Desktop config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "composer": {
      "command": "<absolute-path-to-repo>/.venv/bin/composer-mcp",
      "env": {
        "COMPOSER_BASE": "http://localhost:18080",
        "COMPOSER_CONTEXT_PATH": "/composer",
        "COMPOSER_USER": "admin",
        "COMPOSER_PASSWORD": "<your-composer-admin-password>"
      }
    }
  }
}
```

## Testing

```bash
.venv/bin/python -m tests.smoke
```

The smoke test runs `composer_introspect` against the configured instance.

## Tools

43 tools as of v0.2:

| Category | Tools |
|---|---|
| Discovery | `composer_introspect` |
| Connections | `composer_list_connection_types`, `composer_get_connection_type`, `composer_list_connections`, `composer_get_connection`, `composer_create_connection`, `composer_delete_connection` |
| Sources | `composer_list_sources`, `composer_get_source`, `composer_get_source_fields`, `composer_get_source_visual_types`, `composer_get_initial_visual`, `composer_create_source`, `composer_create_source_v2`, `composer_update_source`, `composer_describe_entity`, `composer_delete_source` |
| Custom metrics | `composer_list_custom_metrics`, `composer_add_custom_metric`, `composer_delete_custom_metric` |
| Migration | `composer_export_sources`, `composer_import_sources` |
| Visuals | `composer_list_visuals`, `composer_get_visual`, `composer_create_visual`, `composer_delete_visual`, `composer_clone_visual_for_dashboard`, `composer_create_visual_pair` |
| Dashboards | `composer_list_dashboards`, `composer_get_dashboard`, `composer_create_dashboard`, `composer_widget_id`, `composer_delete_dashboard` |
| Accounts (multi-tenant) | `composer_list_accounts`, `composer_create_account`, `composer_get_account_users`, `composer_get_account_admins`, `composer_add_users_to_account`, `composer_add_admins_to_account`, `composer_switch_tenant`, `composer_share_dashboard` |
| Tokens | `composer_mint_push_token`, `composer_mint_pull_token` |

`composer_create_visual_pair` builds two copies of the same template at
once: a `TOP`-level visual visible in the Visual Gallery for browsing or
editing standalone, plus an `IN_DASHBOARD`-level twin ready to embed in a
dashboard. Composer rejects sharing a single visual across dashboards, so
this pairing pattern is the right shape for any dashboard-targeted build.

## Cookbook

### Cross-warehouse source (Snowflake + BigQuery)

```python
from composer_mcp.tools import sources

# 1. Probe each entity for native fields
perf_fields = await sources.describe_entity(client, sf_conn_id, "PUBLIC", "DAILY_PERFORMANCE")
attrs_fields = await sources.describe_entity(client, bq_conn_id, "agile-tracker-403309.otto_demo", "article_attributes")

# 2. Convert to source-create shape and dedupe collisions
entities = [
    ("perf",  "Daily Performance",  [sources.to_native_field(f, "perf")  for f in perf_fields]),
    ("attrs", "Article Attributes", [sources.to_native_field(f, "attrs") for f in attrs_fields]),
]
deduped, rename_map = sources.dedupe_native_fields(entities)

# 3. Build the v2 body with a LEFT JOIN
body = {
    "name": "Cross-Warehouse Layer",
    "storage": {
        "dataEntities": [
            {"id": "perf",  "name": "Daily Performance", "type": "SINGLE_COLLECTION",
             "singleCollection": {"connectionId": sf_conn_id, "schema": "PUBLIC", "collection": "DAILY_PERFORMANCE"},
             "nativeFields": deduped[0]},
            {"id": "attrs", "name": "Article Attributes", "type": "SINGLE_COLLECTION",
             "singleCollection": {"connectionId": bq_conn_id, "schema": "agile-tracker-403309.otto_demo", "collection": "article_attributes"},
             "nativeFields": deduped[1]},
        ],
        "joins": [{
            "type": "LEFT",
            "leftDataEntity": {"dataEntityId": "perf", "dimension": False},
            "rightDataEntity": {"dataEntityId": "attrs", "dimension": True},
            "conditions": [{
                "leftFieldName":  sources.join_field_name(rename_map, "perf",  "article_id"),
                "rightFieldName": sources.join_field_name(rename_map, "attrs", "article_id"),
            }],
        }],
    },
}
result = await sources.create_source_v2(client, body)
```

Quirks the helpers handle:
- Snowflake column names get lowercased on introspection (originals in
  `origin.nativeOrigin.originalName`). Use lowercase in join conditions.
- BigQuery `schema` must be `project.dataset` format, not just `dataset`.
- Field-name collisions across joined entities are auto-prefixed
  (`partners_partner_id`) so Composer's "globally unique within source"
  rule is satisfied.

### Custom metric with safe division

```python
from composer_mcp.tools import sources

await sources.add_custom_metric(
    client, source_id,
    name="conversion_rate",
    label="Conversion Rate",
    expression=sources.safe_div_expression("SUM(conversions)", "SUM(clicks)"),
    number_format="PERCENT",  # preset; see sources.NUMBER_FORMATS
)
```

Composer's expression syntax does NOT support `NULLIF`. Use
`safe_div_expression()` (`CASE WHEN denom > 0 THEN num/denom ELSE 0 END`)
for every divide-by-row-aggregate metric.

Number-format quirks `add_custom_metric` shields you from:
- `CURRENCY` requires `currencyCode` AND `standardUnit`
- `PERCENTAGE` REJECTS `standardUnit` (use `PCT` preset)
- `PLAIN` requires `standardUnit`

### Cross-tenant migration (the only working path for connection sharing)

Composer 25 has no UI to share a connection instance between tenants. The
official mechanism is the sources/migration API. The export bundles the
source AND its referenced connection — including the encrypted password,
which is portable across tenants on the same Composer instance.

```python
from composer_mcp.tools import accounts, sources

# 1. As a user with read access on the source, export
await accounts.switch_tenant(client, source_tenant_id)
payload = await sources.export_sources(client, ["src_id_1", "src_id_2"])

# 2. As a user with admin in the target tenant, import
await accounts.switch_tenant(client, target_tenant_id)
result = await sources.import_sources(client, payload, account_id=target_tenant_id)
# result.sources[*].id  -> new source ids in target tenant
# result.connections[*].id -> new connection ids (preserving original names)
```

Caveats:
- Export requires `read` permission on each source PLUS `ROLE_MANAGE_CONNECTIONS`.
- Import targets the calling user's active tenant by default; pass
  `account_id` to override.
- Cross-INSTANCE migration is NOT supported (encryption keys differ).

### Dashboard with synchronised time window

```python
from composer_mcp.tools import dashboards, visuals

# Build dashboard normally, then for every widget visual:
v = await visuals.get_visual(client, visual_id)
v.setdefault("controlsCfg", {}).setdefault("timeControlCfg", {}).update({
    "from": "+$start_of_data",
    "to": "+$end_of_data",
    "timeField": "date",
})
await client.put(f"/visuals/{visual_id}", v)

# Field link so a filter widget scopes everything else:
field_link = dashboards.make_field_link("Campaign Type", source_id, "campaign_type")
# Pass into dashboard body's `fieldLinks` array.
```

Time-token reference: `+$start_of_data`, `+$end_of_data`,
`+$end_of_data_-1_week`, `+$end_of_data_-1_month`, etc.

### Multi-tenant setup pattern

```python
from composer_mcp.tools import accounts

# 1. Create the tenant (note the AccountUserResource shape)
acct = await accounts.create_account(client, name="Otto")

# 2. Add yourself as a member, then promote to admin (member-then-admin order
#    matters — the admin PUT validates membership)
me = {"id": "<your-user-id>", "name": "<your-username>"}
await accounts.add_users_to_account(client, acct["id"], [me])
await accounts.add_admins_to_account(client, acct["id"], [me])

# 3. Switch active context into the new tenant
await accounts.switch_tenant(client, acct["id"])
```

Cross-tenant user adds (importing a user from another tenant) require a
Symphony Global Administrator. A regular tenant admin can only add users
already in their own tenant.

## See also

Other Logi Symphony / Simba Intelligence developer toolkit components in the
same org:

- [`isw-da/symphony-dashboard-builder-skill`](https://github.com/isw-da/symphony-dashboard-builder-skill)
  — the procedural skill this MCP is built on. Useful as a reference when the
  MCP doesn't cover an edge case.
- [`isw-da/simba-intelligence-skill`](https://github.com/isw-da/simba-intelligence-skill)
  — Claude skill for installing, configuring, and troubleshooting Simba
  Intelligence on Kubernetes.
- [`isw-da/edc-graphql`](https://github.com/isw-da/edc-graphql) — Java
  Enterprise Data Connector that lets Composer / Simba Intelligence query
  any GraphQL API.
