"""Composer MCP server.

Wires the tool modules into MCP tool handlers, talks to Composer over the
documented v25 REST API, returns plain JSON for the model to reason over.

Run via:
    COMPOSER_BASE=http://localhost:18080 \\
    COMPOSER_USER=admin \\
    COMPOSER_PASSWORD=... \\
    composer-mcp

Or under Claude Desktop / Code via the MCP server config:
    {
      "mcpServers": {
        "composer": {
          "command": "/Users/aminhasan/composer-mcp/.venv/bin/composer-mcp",
          "env": { "COMPOSER_BASE": "...", "COMPOSER_USER": "...", "COMPOSER_PASSWORD": "..." }
        }
      }
    }
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .client import ComposerClient, ComposerConfig, ComposerError
from .tools import accounts, connections, dashboards, discovery, sources, tokens, visuals


# ----------------------------- tool registry -----------------------------
#
# Each entry: (mcp tool name, description, input schema, handler).
# Handlers receive (client, args) and return a JSON-serialisable value.

def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TOOLS: list[dict[str, Any]] = [
    # --- discovery ---
    {
        "name": "composer_introspect",
        "description": (
            "One-shot introspection of a Composer instance. Returns connections, "
            "sources (with fields), dashboards, and accounts in a single payload. "
            "Use this first when starting work on an unfamiliar instance."
        ),
        "schema": _schema({"max_sources": {"type": "integer", "default": 10}}),
        "handler": lambda c, a: discovery.introspect_instance(c, a.get("max_sources", 10)),
    },
    # --- connections ---
    {
        "name": "composer_list_connection_types",
        "description": "List installed connector types (Snowflake, BigQuery, Postgres, etc.).",
        "schema": _schema({}),
        "handler": lambda c, a: connections.list_connection_types(c),
    },
    {
        "name": "composer_get_connection_type",
        "description": "Get full schema for a connector type, including required parameters.",
        "schema": _schema({"type_id": {"type": "string"}}, ["type_id"]),
        "handler": lambda c, a: connections.get_connection_type(c, a["type_id"]),
    },
    {
        "name": "composer_list_connections",
        "description": "List all configured data connections.",
        "schema": _schema({}),
        "handler": lambda c, a: connections.list_connections(c),
    },
    {
        "name": "composer_get_connection",
        "description": "Full details of one connection (passwords masked).",
        "schema": _schema({"connection_id": {"type": "string"}}, ["connection_id"]),
        "handler": lambda c, a: connections.get_connection(c, a["connection_id"]),
    },
    {
        "name": "composer_create_connection",
        "description": (
            "Create a new data connection. Use composer_get_connection_type first "
            "to see required parameters for the chosen connector."
        ),
        "schema": _schema(
            {
                "name": {"type": "string"},
                "connection_type_id": {"type": "string"},
                "sub_storage_type": {"type": "string", "description": "e.g. SNOWFLAKE, BIGQUERY"},
                "parameters": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Map of param key to value, e.g. JDBC_URL/USER_NAME/PASSWORD.",
                },
            },
            ["name", "connection_type_id", "sub_storage_type", "parameters"],
        ),
        "handler": lambda c, a: connections.create_connection(
            c, a["name"], a["connection_type_id"], a["sub_storage_type"], a["parameters"]
        ),
    },
    {
        "name": "composer_delete_connection",
        "description": "Delete a connection by ID.",
        "schema": _schema({"connection_id": {"type": "string"}}, ["connection_id"]),
        "handler": lambda c, a: connections.delete_connection(c, a["connection_id"]),
    },
    # --- sources ---
    {
        "name": "composer_list_sources",
        "description": "List all data sources (queryable semantic-layer objects).",
        "schema": _schema({}),
        "handler": lambda c, a: sources.list_sources(c),
    },
    {
        "name": "composer_get_source",
        "description": "Get full details of a source.",
        "schema": _schema({"source_id": {"type": "string"}}, ["source_id"]),
        "handler": lambda c, a: sources.get_source(c, a["source_id"]),
    },
    {
        "name": "composer_get_source_fields",
        "description": "List fields exposed by a source — needed before creating visuals.",
        "schema": _schema({"source_id": {"type": "string"}}, ["source_id"]),
        "handler": lambda c, a: sources.get_source_fields(c, a["source_id"]),
    },
    {
        "name": "composer_get_source_visual_types",
        "description": "List visual types compatible with a source (KPI, LINE_CHART, etc.).",
        "schema": _schema({"source_id": {"type": "string"}}, ["source_id"]),
        "handler": lambda c, a: sources.get_source_visual_types(c, a["source_id"]),
    },
    {
        "name": "composer_get_initial_visual",
        "description": (
            "CRITICAL: fetch the fully-initialised visual template for a "
            "(source, visualType) pair. ALWAYS use this before creating a visual. "
            "Hand-crafting visual JSON crashes the Composer frontend."
        ),
        "schema": _schema(
            {
                "source_id": {"type": "string"},
                "visual_type_id": {"type": "string"},
            },
            ["source_id", "visual_type_id"],
        ),
        "handler": lambda c, a: sources.get_initial_visual(c, a["source_id"], a["visual_type_id"]),
    },
    {
        "name": "composer_create_source",
        "description": (
            "Create a data source against a single table or view in a connection. "
            "Composer auto-introspects fields from the underlying schema. "
            "Returns the source object with id, native fields, and storage metadata."
        ),
        "schema": _schema(
            {
                "name": {"type": "string"},
                "connection_id": {"type": "string"},
                "schema": {"type": "string", "description": "Database schema name (e.g. 'opc')"},
                "table": {"type": "string", "description": "Table or view name (e.g. 'v_combined_metrics')"},
                "description": {"type": "string", "default": ""},
            },
            ["name", "connection_id", "schema", "table"],
        ),
        "handler": lambda c, a: sources.create_source(
            c, a["name"], a["connection_id"], a["schema"], a["table"], a.get("description", "")
        ),
    },
    {
        "name": "composer_delete_source",
        "description": "Delete a data source.",
        "schema": _schema({"source_id": {"type": "string"}}, ["source_id"]),
        "handler": lambda c, a: sources.delete_source(c, a["source_id"]),
    },
    {
        "name": "composer_create_source_v2",
        "description": (
            "Create a multi-entity source with full body control (joins, "
            "cross-warehouse entities, custom nativeFields). Use this when "
            "composer_create_source's single-table form isn't enough. "
            "See README for the SourceResource shape and gotchas around "
            "field-name collisions and cross-warehouse joins."
        ),
        "schema": _schema({"body": {"type": "object"}}, ["body"]),
        "handler": lambda c, a: sources.create_source_v2(c, a["body"]),
    },
    {
        "name": "composer_update_source",
        "description": (
            "Replace an existing source's full body (PUT). Useful for adding "
            "an entity + join to an existing source in place — preserves "
            "the source id so visuals already bound to it keep working."
        ),
        "schema": _schema(
            {"source_id": {"type": "string"}, "body": {"type": "object"}},
            ["source_id", "body"],
        ),
        "handler": lambda c, a: sources.update_source(c, a["source_id"], a["body"]),
    },
    {
        "name": "composer_describe_entity",
        "description": (
            "Probe a single SINGLE_COLLECTION entity for its native fields. "
            "Returns the flat describe shape; pass each field through "
            "to_native_field() before embedding into a v2 source body."
        ),
        "schema": _schema(
            {
                "connection_id": {"type": "string"},
                "schema": {"type": "string"},
                "collection": {"type": "string"},
            },
            ["connection_id", "schema", "collection"],
        ),
        "handler": lambda c, a: sources.describe_entity(
            c, a["connection_id"], a["schema"], a["collection"]
        ),
    },
    # --- custom metrics ---
    {
        "name": "composer_list_custom_metrics",
        "description": "List custom (calculated) metrics on a source.",
        "schema": _schema({"source_id": {"type": "string"}}, ["source_id"]),
        "handler": lambda c, a: sources.list_custom_metrics(c, a["source_id"]),
    },
    {
        "name": "composer_add_custom_metric",
        "description": (
            "Add a calculated metric to a source. `expression` is in "
            "Composer's expression syntax (SUM, AVG, COUNT, CASE WHEN, "
            "COALESCE, +-*/, ROUND etc; NULLIF is NOT supported). "
            "`number_format` may be a NumberFormatResource dict or a preset "
            "key: 'EUR', 'USD', 'GBP', 'PERCENT', 'RATIO', 'INTEGER'. "
            "For divide-by-zero safety wrap with: "
            "CASE WHEN denom > 0 THEN num / denom ELSE 0 END."
        ),
        "schema": _schema(
            {
                "source_id": {"type": "string"},
                "name": {"type": "string"},
                "label": {"type": "string"},
                "expression": {"type": "string"},
                "number_format": {
                    "description": "Either a literal NumberFormatResource dict or a preset name.",
                },
                "visible": {"type": "boolean", "default": True},
            },
            ["source_id", "name", "label", "expression"],
        ),
        "handler": lambda c, a: sources.add_custom_metric(
            c,
            a["source_id"],
            a["name"],
            a["label"],
            a["expression"],
            a.get("number_format"),
            a.get("visible", True),
        ),
    },
    {
        "name": "composer_delete_custom_metric",
        "description": "Delete a custom metric by name from a source.",
        "schema": _schema(
            {"source_id": {"type": "string"}, "name": {"type": "string"}},
            ["source_id", "name"],
        ),
        "handler": lambda c, a: sources.delete_custom_metric(c, a["source_id"], a["name"]),
    },
    # --- cross-tenant migration (export/import) ---
    {
        "name": "composer_export_sources",
        "description": (
            "Export sources (with their referenced connections, encrypted "
            "passwords preserved) as a portable JSON payload. Pair with "
            "composer_import_sources(account_id=...) to clone into a "
            "different tenant on the SAME Composer instance. This is the "
            "official cross-tenant migration mechanism — Composer 25 has no "
            "UI to share connection instances directly."
        ),
        "schema": _schema(
            {"source_ids": {"type": "array", "items": {"type": "string"}}},
            ["source_ids"],
        ),
        "handler": lambda c, a: sources.export_sources(c, a["source_ids"]),
    },
    {
        "name": "composer_import_sources",
        "description": (
            "Import a previously-exported source bundle. Pass account_id to "
            "target a different tenant (the cross-tenant migration path). "
            "Composer auto-recreates referenced connections."
        ),
        "schema": _schema(
            {
                "payload": {"type": "object"},
                "account_id": {"type": "string"},
                "suppress_warnings": {"type": "boolean", "default": True},
                "enable_default_read": {"type": "boolean", "default": True},
            },
            ["payload"],
        ),
        "handler": lambda c, a: sources.import_sources(
            c,
            a["payload"],
            a.get("account_id"),
            a.get("suppress_warnings", True),
            a.get("enable_default_read", True),
        ),
    },
    # --- visuals ---
    {
        "name": "composer_list_visuals",
        "description": "List all visuals.",
        "schema": _schema({}),
        "handler": lambda c, a: visuals.list_visuals(c),
    },
    {
        "name": "composer_get_visual",
        "description": "Get full visual JSON.",
        "schema": _schema({"visual_id": {"type": "string"}}, ["visual_id"]),
        "handler": lambda c, a: visuals.get_visual(c, a["visual_id"]),
    },
    {
        "name": "composer_create_visual",
        "description": (
            "Create a visual from a (modified) initial-visual template. "
            "Set level='IN_DASHBOARD' on the template before calling. "
            "Returns the visual ID for use in dashboards."
        ),
        "schema": _schema(
            {"visual_template": {"type": "object"}}, ["visual_template"]
        ),
        "handler": lambda c, a: visuals.create_visual(c, a["visual_template"]),
    },
    {
        "name": "composer_delete_visual",
        "description": "Delete a visual.",
        "schema": _schema({"visual_id": {"type": "string"}}, ["visual_id"]),
        "handler": lambda c, a: visuals.delete_visual(c, a["visual_id"]),
    },
    {
        "name": "composer_clone_visual_for_dashboard",
        "description": (
            "Clone a TOP-level (Gallery) visual into an IN_DASHBOARD copy "
            "ready to embed in a dashboard. Use this whenever you have a "
            "Gallery template you want to put on a dashboard."
        ),
        "schema": _schema({"top_visual_id": {"type": "string"}}, ["top_visual_id"]),
        "handler": lambda c, a: visuals.clone_for_dashboard(c, a["top_visual_id"]),
    },
    {
        "name": "composer_create_visual_pair",
        "description": (
            "Create both a TOP (Gallery) and IN_DASHBOARD copy of a visual "
            "from one template. Best-practice flow: visual is browseable "
            "standalone AND used inside a dashboard. Returns "
            "{top_id, dashboard_id}."
        ),
        "schema": _schema({"visual_template": {"type": "object"}}, ["visual_template"]),
        "handler": lambda c, a: visuals.create_visual_pair(c, a["visual_template"]),
    },
    # --- dashboards ---
    {
        "name": "composer_list_dashboards",
        "description": "List all dashboards.",
        "schema": _schema({}),
        "handler": lambda c, a: dashboards.list_dashboards(c),
    },
    {
        "name": "composer_get_dashboard",
        "description": "Get a dashboard's full configuration.",
        "schema": _schema({"dashboard_id": {"type": "string"}}, ["dashboard_id"]),
        "handler": lambda c, a: dashboards.get_dashboard(c, a["dashboard_id"]),
    },
    {
        "name": "composer_create_dashboard",
        "description": (
            "Create a dashboard with a list of widgets. Each widget must include "
            "id (use composer_widget_id), name, visualId, and layout {row,col,rowSpan,colSpan}. "
            "Visuals must be created first via composer_create_visual."
        ),
        "schema": _schema(
            {
                "name": {"type": "string"},
                "description": {"type": "string", "default": ""},
                "widgets": {"type": "array", "items": {"type": "object"}},
                "is_responsive": {"type": "boolean", "default": True},
                "is_free_form": {"type": "boolean", "default": False},
            },
            ["name", "widgets"],
        ),
        "handler": lambda c, a: dashboards.create_dashboard(
            c,
            a["name"],
            a["widgets"],
            a.get("description", ""),
            a.get("is_responsive", True),
            a.get("is_free_form", False),
        ),
    },
    {
        "name": "composer_widget_id",
        "description": "Generate a 32-char hex widget ID for use in composer_create_dashboard.",
        "schema": _schema({}),
        "handler": lambda c, a: {"widget_id": dashboards.widget_id()},
    },
    {
        "name": "composer_delete_dashboard",
        "description": "Delete a dashboard.",
        "schema": _schema({"dashboard_id": {"type": "string"}}, ["dashboard_id"]),
        "handler": lambda c, a: dashboards.delete_dashboard(c, a["dashboard_id"]),
    },
    # --- accounts (multi-tenancy) ---
    {
        "name": "composer_list_accounts",
        "description": "List tenant accounts.",
        "schema": _schema({}),
        "handler": lambda c, a: accounts.list_accounts(c),
    },
    {
        "name": "composer_create_account",
        "description": (
            "Create a tenant. The body is the AccountUserResource shape: "
            "`{account: {name, disabled}, users: []}`. You can pre-attach "
            "existing users in the same call by passing them; otherwise add "
            "them later via composer_add_users_to_account."
        ),
        "schema": _schema(
            {
                "name": {"type": "string"},
                "users": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Optional list of {id, name} users to attach at create time.",
                },
            },
            ["name"],
        ),
        "handler": lambda c, a: accounts.create_account(c, a["name"], a.get("users")),
    },
    {
        "name": "composer_get_account_users",
        "description": "List users currently in a tenant.",
        "schema": _schema({"account_id": {"type": "string"}}, ["account_id"]),
        "handler": lambda c, a: accounts.get_account_users(c, a["account_id"]),
    },
    {
        "name": "composer_get_account_admins",
        "description": "List admins of a tenant.",
        "schema": _schema({"account_id": {"type": "string"}}, ["account_id"]),
        "handler": lambda c, a: accounts.get_account_admins(c, a["account_id"]),
    },
    {
        "name": "composer_add_users_to_account",
        "description": (
            "Replace a tenant's user list (PUT). `users` is a flat array of "
            "{id, name}. PUT REPLACES — fetch the existing list first and "
            "append, otherwise everyone except the passed users gets evicted. "
            "Cross-tenant adds (importing a user from a different tenant) "
            "require Symphony Global Administrator; per-tenant admins can "
            "only add users already in their own tenant."
        ),
        "schema": _schema(
            {
                "account_id": {"type": "string"},
                "users": {"type": "array", "items": {"type": "object"}},
            },
            ["account_id", "users"],
        ),
        "handler": lambda c, a: accounts.add_users_to_account(c, a["account_id"], a["users"]),
    },
    {
        "name": "composer_add_admins_to_account",
        "description": (
            "Replace a tenant's admin list (PUT). Each user must already be "
            "a member; otherwise this returns 400 'doesn't belong to account'. "
            "Same PUT-replace semantics as composer_add_users_to_account."
        ),
        "schema": _schema(
            {
                "account_id": {"type": "string"},
                "users": {"type": "array", "items": {"type": "object"}},
            },
            ["account_id", "users"],
        ),
        "handler": lambda c, a: accounts.add_admins_to_account(c, a["account_id"], a["users"]),
    },
    {
        "name": "composer_switch_tenant",
        "description": (
            "Switch the active tenant context for the current session. After "
            "switching, all subsequent /api/* calls run in the target tenant's "
            "scope (its sources, dashboards, connections). Returns 400 if the "
            "calling user is not a member of the target tenant."
        ),
        "schema": _schema({"account_id": {"type": "string"}}, ["account_id"]),
        "handler": lambda c, a: accounts.switch_tenant(c, a["account_id"]),
    },
    {
        "name": "composer_share_dashboard",
        "description": (
            "Share a dashboard with users/groups/accounts (ACL bulk update). "
            "sids is a list like [{type: 'group', name: 'analysts'}]."
        ),
        "schema": _schema(
            {
                "dashboard_id": {"type": "string"},
                "sids": {"type": "array", "items": {"type": "object"}},
                "permission": {"type": "string", "default": "read"},
            },
            ["dashboard_id", "sids"],
        ),
        "handler": lambda c, a: accounts.share_dashboard(
            c, a["dashboard_id"], a["sids"], a.get("permission", "read")
        ),
    },
    # --- trusted access tokens (impersonation, embedding) ---
    {
        "name": "composer_mint_push_token",
        "description": (
            "Mint a push token impersonating a user. Used for embedded scenarios "
            "and for UC4 'replicate partner view' troubleshooting."
        ),
        "schema": _schema(
            {
                "username": {"type": "string"},
                "account": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
                "attributes": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            ["username", "account"],
        ),
        "handler": lambda c, a: tokens.mint_push_token(
            c,
            a["username"],
            a["account"],
            a.get("roles", ["viewer"]),
            a.get("attributes"),
        ),
    },
    {
        "name": "composer_mint_pull_token",
        "description": "Mint a pull token by looking up an existing user.",
        "schema": _schema(
            {"username": {"type": "string"}, "account": {"type": "string"}},
            ["username", "account"],
        ),
        "handler": lambda c, a: tokens.mint_pull_token(c, a["username"], a["account"]),
    },
]


def _format_result(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value)


async def amain() -> None:
    cfg = ComposerConfig.from_env()
    server: Server = Server("composer-mcp")
    by_name = {t["name"]: t for t in TOOLS}

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(name=t["name"], description=t["description"], inputSchema=t["schema"])
            for t in TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        tool = by_name.get(name)
        if tool is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        client = ComposerClient(cfg)
        try:
            result = await tool["handler"](client, arguments or {})
            return [TextContent(type="text", text=_format_result(result))]
        except ComposerError as e:
            return [
                TextContent(
                    type="text",
                    text=f"Composer API error {e.status}: {e}\n\nBody: {_format_result(e.body)}",
                )
            ]
        except Exception as e:
            return [TextContent(type="text", text=f"Tool {name} failed: {type(e).__name__}: {e}")]
        finally:
            await client.aclose()

    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
