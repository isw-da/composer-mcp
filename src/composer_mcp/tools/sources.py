"""Source (semantic-layer) management.

A "source" in Composer is a queryable object built on top of one or more
connections, exposing a set of fields with friendly names and types. Visuals
reference source IDs, not raw tables.

Multi-entity sources (cross-table, cross-warehouse joins) work via the v2
storage shape: `storage.dataEntities[]` plus `storage.joins[]`. Each join is
a `SourceJoinResource` with INNER/LEFT/FULL_OUTER, left/right entity ids,
and a list of `{leftFieldName, rightFieldName}` conditions (EQUALS only).

Cross-warehouse joins (e.g. Snowflake fact + BigQuery dimension) work in
Composer 25 — each entity carries its own `connectionId`. Composer
federates the query at runtime.

Real-world quirks captured here:

* The `/sources/data-entities/describe` response uses a flat field shape
  (`{type, name, originalFieldName, label}`), but `POST /sources` expects
  the nested SourceFieldResource shape with `origin.nativeOrigin.{...}` and
  `dataType` instead of `type`. Use `to_native_field()` to convert.

* Composer requires globally unique field names within a single source. If
  the same column (e.g. `partner_id`) appears in multiple joined entities,
  the second occurrence MUST be renamed (e.g. `partners_partner_id`). Use
  `dedupe_native_fields()` to auto-prefix collisions.

* Snowflake column names are lowercased on introspection. Original uppercase
  is preserved in `origin.nativeOrigin.originalName`. Join conditions
  reference the lowercased name (`partner_id`, not `PARTNER_ID`).

* BigQuery `schema` must be `project.dataset` format — not just `dataset`.

* Custom metric expressions: Composer's syntax does NOT support `NULLIF`.
  Guard against divide-by-zero with `CASE WHEN denom > 0 THEN ... ELSE 0 END`.
  See `safe_div_expression()`.

* Custom metric `numberFormat`: `CURRENCY` requires `currencyCode` and
  `standardUnit`. `PERCENTAGE` rejects `standardUnit`. `PLAIN` requires
  `standardUnit`. See `NUMBER_FORMATS` for ready-made presets.

* Cross-tenant migration: connection-instance sharing has no UI in Composer
  25. The official path is the sources/migration API: `GET /sources/export`
  + `POST /sources/import?accountId=...`. The export bundles the source AND
  its referenced connection (with the encrypted password preserved across
  tenants in the same Composer instance). See `export_sources` /
  `import_sources` below.
"""

from __future__ import annotations

from typing import Any

from ..client import ComposerClient


# ----------------------------------------------------------------------
# Listing / introspection
# ----------------------------------------------------------------------


async def list_sources(client: ComposerClient) -> list[dict]:
    items = await client.get_list("/sources")
    return [
        {
            "id": s["id"],
            "name": s.get("name"),
            "connectionId": s.get("connectionId"),
        }
        for s in items
        if isinstance(s, dict)
    ]


async def get_source(client: ComposerClient, source_id: str) -> dict:
    return await client.get(f"/sources/{source_id}")


async def get_source_fields(client: ComposerClient, source_id: str) -> list[dict]:
    """Return fields exposed by this source — name, type, visibility."""
    items = await client.get_list(f"/sources/{source_id}/fields")
    return [
        {
            "name": f.get("name"),
            "label": f.get("label"),
            "type": f.get("type") or f.get("dataType"),
            "visible": f.get("visible", True),
        }
        for f in items
        if isinstance(f, dict)
    ]


async def get_source_visual_types(client: ComposerClient, source_id: str) -> list[dict]:
    """List visual types compatible with this source.

    Returned items use `visualTypeId` as the ID field (NOT `id`) — passing
    the wrong field is the most common bug per the skill.
    """
    items = await client.get_list(f"/sources/{source_id}/visual-types")
    return [
        {
            "visualTypeId": v.get("visualTypeId") or v.get("id"),
            "name": v.get("name"),
            "type": v.get("type"),
        }
        for v in items
        if isinstance(v, dict)
    ]


async def get_initial_visual(
    client: ComposerClient, source_id: str, visual_type_id: str
) -> dict:
    """Fetch a fully-initialised visual template.

    CRITICAL: this is the only safe way to construct a visual programmatically.
    Hand-crafting visual JSON crashes the Composer frontend with
    "Cannot read properties of undefined (reading 'values')".
    """
    return await client.get(
        f"/sources/{source_id}/visual-types/{visual_type_id}/initial-visual"
    )


# ----------------------------------------------------------------------
# Multi-entity helpers
# ----------------------------------------------------------------------


async def describe_entity(
    client: ComposerClient,
    connection_id: str,
    schema: str,
    collection: str,
) -> list[dict]:
    """Probe a single SINGLE_COLLECTION entity for its native fields.

    Wraps `POST /sources/data-entities/describe`. Returns the flat describe
    shape (`{type, originalFieldName, name, label}`). Run through
    `to_native_field()` before embedding into a source create body.
    """
    body = {
        "type": "SINGLE_COLLECTION",
        "singleCollection": {
            "connectionId": connection_id,
            "schema": schema,
            "collection": collection,
        },
    }
    resp = await client.post("/sources/data-entities/describe", body)
    return resp.get("content") or resp.get("nativeFields") or []


def to_native_field(describe_field: dict, entity_id: str) -> dict:
    """Translate a `data-entities/describe` field into a SourceFieldResource.

    The describe and create endpoints disagree on shape. describe returns:
        {type, name, originalFieldName, label}
    create wants:
        {origin: {type:'NATIVE', nativeOrigin: {originalName, originalType, dataEntityId}},
         name, label, dataType, visible}
    """
    return {
        "origin": {
            "type": "NATIVE",
            "nativeOrigin": {
                "originalName": describe_field.get("originalFieldName") or describe_field.get("name"),
                "originalType": describe_field.get("type"),
                "dataEntityId": entity_id,
            },
        },
        "name": describe_field.get("name"),
        "label": describe_field.get("label"),
        "dataType": describe_field.get("type"),
        "visible": True,
    }


def dedupe_native_fields(
    entities: list[tuple[str, str, list[dict]]]
) -> tuple[list[list[dict]], dict[str, dict[str, str]]]:
    """Apply prefix renaming to colliding field names across joined entities.

    Composer requires globally unique field names within a source. When the
    same column (e.g. `partner_id`) appears in multiple entities, every
    occurrence after the first is renamed to `<entity_id>_<column>` and the
    label is annotated with the entity name.

    Args:
      entities: list of `(entity_id, entity_name, native_fields)` tuples in
                preferred-priority order. Fields on the FIRST entity keep
                their original names; later entities lose the duplicates.

    Returns:
      `(deduped_fields_by_entity, rename_map_by_entity)`. The rename map lets
      callers rewrite join-condition field names accordingly.
    """
    seen: set[str] = set()
    deduped: list[list[dict]] = []
    rename_map: dict[str, dict[str, str]] = {}
    for entity_id, entity_name, fields in entities:
        out: list[dict] = []
        renames: dict[str, str] = {}
        for f in fields:
            new = dict(f)
            if new["name"] in seen:
                renamed = f"{entity_id}_{new['name']}"
                renames[new["name"]] = renamed
                new["name"] = renamed
                if new.get("label"):
                    new["label"] = f"{entity_name}: {new['label']}"
            seen.add(new["name"])
            out.append(new)
        deduped.append(out)
        rename_map[entity_id] = renames
    return deduped, rename_map


def join_field_name(rename_map: dict[str, dict[str, str]], entity_id: str, original: str) -> str:
    """Look up a possibly-renamed field name for use in join conditions."""
    return rename_map.get(entity_id, {}).get(original, original)


# ----------------------------------------------------------------------
# Source CRUD
# ----------------------------------------------------------------------


async def create_source(
    client: ComposerClient,
    name: str,
    connection_id: str,
    schema: str,
    table: str,
    description: str = "",
) -> dict:
    """Create a new SINGLE_COLLECTION source against one table.

    For multi-entity sources with joins, build the body manually and call
    `create_source_v2` directly.
    """
    body = {
        "name": name,
        "description": description,
        "storage": {
            "dataEntities": [
                {
                    "id": table,
                    "name": table,
                    "type": "SINGLE_COLLECTION",
                    "singleCollection": {
                        "connectionId": connection_id,
                        "schema": schema,
                        "collection": table,
                    },
                }
            ],
            "joins": [],
        },
    }
    return await client.post("/sources", body)


async def create_source_v2(client: ComposerClient, body: dict) -> dict:
    """Create a source with a full body (multiple entities, joins, etc).

    Body should follow `SourceResource`: `{name, description, storage:
    {dataEntities[], joins[]}, tags}`. nativeFields on each entity are
    REQUIRED for join validation — pre-introspect with `describe_entity` and
    convert via `to_native_field`.
    """
    return await client.post("/sources", body)


async def update_source(client: ComposerClient, source_id: str, body: dict) -> dict:
    """Replace an existing source's full body.

    Useful for adding entities / joins to an existing source in place
    (preserving the source id and any visuals already bound to it).
    """
    return await client.put(f"/sources/{source_id}", body)


async def delete_source(client: ComposerClient, source_id: str) -> dict:
    await client.delete(f"/sources/{source_id}")
    return {"deleted": source_id}


# ----------------------------------------------------------------------
# Custom metrics
# ----------------------------------------------------------------------


# Ready-made numberFormat presets. Quirk: PERCENTAGE rejects `standardUnit`,
# CURRENCY and PLAIN require it. Discovered the hard way.
NUMBER_FORMATS = {
    "EUR": {"type": "CURRENCY", "currencyCode": "EUR", "decimals": 2, "separator": True, "standardUnit": "NONE"},
    "USD": {"type": "CURRENCY", "currencyCode": "USD", "decimals": 2, "separator": True, "standardUnit": "NONE"},
    "GBP": {"type": "CURRENCY", "currencyCode": "GBP", "decimals": 2, "separator": True, "standardUnit": "NONE"},
    "PERCENT": {"type": "PERCENTAGE", "decimals": 2, "separator": True},
    "RATIO": {"type": "PLAIN", "decimals": 2, "separator": True, "standardUnit": "NONE"},
    "INTEGER": {"type": "PLAIN", "decimals": 0, "separator": True, "standardUnit": "NONE"},
}


def safe_div_expression(numerator: str, denominator: str) -> str:
    """Build a divide-by-zero-safe Composer expression.

    Composer's expression language doesn't support NULLIF. Use CASE WHEN
    instead: `CASE WHEN denom > 0 THEN num / denom ELSE 0 END`. Use this for
    every metric that divides by a sum of integers (clicks, impressions,
    spend, etc.) where zero-denominator rows are plausible.

    Example: `safe_div_expression("SUM(sales_eur)", "SUM(clicks)")` →
    `CASE WHEN SUM(clicks) > 0 THEN SUM(sales_eur) / SUM(clicks) ELSE 0 END`.
    """
    return f"CASE WHEN {denominator} > 0 THEN {numerator} / {denominator} ELSE 0 END"


async def list_custom_metrics(client: ComposerClient, source_id: str) -> list[dict]:
    return await client.get_list(f"/sources/{source_id}/custom-metrics")


async def add_custom_metric(
    client: ComposerClient,
    source_id: str,
    name: str,
    label: str,
    expression: str,
    number_format: dict | str | None = None,
    visible: bool = True,
) -> dict:
    """Create a custom (calculated) metric on a source.

    `expression` is in Composer's expression syntax — supported functions
    include SUM, AVG, MIN, MAX, COUNT, COUNTD, ROUND, CASE WHEN, COALESCE,
    arithmetic operators, plus time helpers. `NULLIF` is NOT supported —
    use `safe_div_expression()` to guard divisions.

    `number_format` may be a literal NumberFormatResource dict or one of the
    keys in `NUMBER_FORMATS` (e.g. `"EUR"`, `"PERCENT"`, `"RATIO"`).
    """
    body: dict[str, Any] = {
        "name": name,
        "label": label,
        "expression": expression,
        "visible": visible,
    }
    if number_format is not None:
        if isinstance(number_format, str):
            if number_format not in NUMBER_FORMATS:
                raise ValueError(
                    f"Unknown number_format preset {number_format!r}. "
                    f"Options: {sorted(NUMBER_FORMATS)}"
                )
            body["numberFormat"] = NUMBER_FORMATS[number_format]
        else:
            body["numberFormat"] = number_format
    return await client.post(f"/sources/{source_id}/custom-metrics", body)


async def delete_custom_metric(
    client: ComposerClient, source_id: str, name: str
) -> dict:
    await client.delete(f"/sources/{source_id}/custom-metrics/{name}")
    return {"deleted": name}


# ----------------------------------------------------------------------
# Cross-tenant migration (export / import)
# ----------------------------------------------------------------------


async def export_sources(client: ComposerClient, source_ids: list[str]) -> dict:
    """Export one or more sources as a portable JSON payload.

    The payload bundles the source definitions AND the referenced connection
    objects, with passwords in Composer's encrypted form. The result is
    importable into another tenant on the SAME Composer instance via
    `import_sources(..., account_id=target)`. Cross-instance import is NOT
    supported (encryption keys differ).

    Required role: `read` on each source + `ROLE_MANAGE_CONNECTIONS`.
    """
    params = [("ids", sid) for sid in source_ids]
    return await client.request("GET", "/sources/export", params=params)


async def import_sources(
    client: ComposerClient,
    payload: dict,
    account_id: str | None = None,
    suppress_warnings: bool = True,
    enable_default_read: bool = True,
) -> dict:
    """Import a previously-exported source bundle into a target tenant.

    `payload` is the full export response from `export_sources`. Pass
    `account_id` to target a tenant other than the caller's active one —
    this is the cross-tenant migration mechanism (the only one supported,
    given Composer 25 has no UI to share connection instances directly).

    Composer recreates referenced connections automatically (with their
    encrypted passwords preserved). Source/connection IDs in the target
    tenant are freshly minted; the caller's mapping of imported names to
    new IDs is in the response under `sources[]` and `connections[]`.

    `suppress_warnings=True` lets the import succeed when the only problems
    are warnings (e.g. duplicate name conflicts handled by Composer).
    `enable_default_read=True` grants every user in the target tenant read
    access on the imported sources — convenient for demo setup.
    """
    params: dict[str, Any] = {
        "suppressWarnings": "true" if suppress_warnings else "false",
        "enableDefaultRead": "true" if enable_default_read else "false",
    }
    if account_id:
        params["accountId"] = account_id
    return await client.post("/sources/import", payload, params=params)


# ----------------------------------------------------------------------
# Backward-compatible alias for the older single-table create
# ----------------------------------------------------------------------

# (Kept on purpose: scripts that imported the old name keep working.)
