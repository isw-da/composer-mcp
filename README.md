# composer-mcp

MCP server that wraps the Logi Composer v25 REST API as MCP tools.

Built on top of the patterns documented in
[`isw-da/symphony-dashboard-builder-skill`](https://github.com/isw-da/symphony-dashboard-builder-skill).
That skill is a 690-line procedural document; this MCP turns those patterns
into proper tools so any Claude session can drive Composer end-to-end without
re-reading the skill each time.

## What it does

- One-shot instance introspection (`composer_introspect`)
- Connection management (Snowflake, BigQuery, Postgres, etc.)
- Source / field discovery, including the safe `initial-visual` workflow
- Visual creation, dashboard creation with widget grid layout
- Multi-tenancy (accounts, dashboard ACL sharing)
- Trusted access tokens (push for impersonation, pull for SSO)

The server enforces the non-negotiable Composer quirks documented in the
skill:

- `application/vnd.composer.v3+json` content type everywhere
- `/discovery/api/...` base path
- Lists unwrapped from `{content: [...]}` shape
- `level: 'IN_DASHBOARD'` validation on visual creation
- 2-element `path` and `params` arrays in dashboard layouts (Composer v25)
- 32-char hex widget IDs

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
the SI-bundled deployment, set `COMPOSER_CONTEXT_PATH=/discovery`. Set
`COMPOSER_BEARER` instead of `COMPOSER_PASSWORD` to use a Trusted Access
token instead of Basic auth.

(stdio mode — wire it into your Claude Desktop or Claude Code config.)

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

30 tools:

| Category | Tools |
|---|---|
| Discovery | `composer_introspect` |
| Connections | `composer_list_connection_types`, `composer_get_connection_type`, `composer_list_connections`, `composer_get_connection`, `composer_create_connection`, `composer_delete_connection` |
| Sources | `composer_list_sources`, `composer_get_source`, `composer_get_source_fields`, `composer_get_source_visual_types`, `composer_get_initial_visual`, `composer_create_source`, `composer_delete_source` |
| Visuals | `composer_list_visuals`, `composer_get_visual`, `composer_create_visual`, `composer_delete_visual`, `composer_clone_visual_for_dashboard`, `composer_create_visual_pair` |
| Dashboards | `composer_list_dashboards`, `composer_get_dashboard`, `composer_create_dashboard`, `composer_widget_id`, `composer_delete_dashboard` |
| Accounts | `composer_list_accounts`, `composer_create_account`, `composer_share_dashboard` |
| Tokens | `composer_mint_push_token`, `composer_mint_pull_token` |

`composer_create_visual_pair` builds two copies of the same template at
once: a `TOP`-level visual visible in the Visual Gallery for browsing or
editing standalone, plus an `IN_DASHBOARD`-level twin ready to embed in a
dashboard. Composer rejects sharing a single visual across dashboards, so
this pairing pattern is the right shape for any dashboard-targeted build.
