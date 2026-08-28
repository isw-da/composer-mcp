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
# Forced filters (row-level security)
#
# A `forcedFilter` on a source is appended to every query against that
# source for users matching the given SID. Combined with push-token
# `groups` or `attributes`, this gives row-level security: a partner
# user only sees rows where partner_id matches their group claim.
#
# Shape (verified against UAT, Composer v25):
#
#   {
#     sid: {type: 'GROUP'|'USER'|'ACCOUNT', principal: '<name>'},
#     filter: {
#       field: 'partner_id',
#       operator: 'EQUALS'|'IN'|'NOT_EQUALS'|'CONTAINS',
#       values: ['<literal>'] | '${User.<attr>}',
#     },
#   }
#
# `${User.<attr>}` interpolates the attribute the push token carried.
# `${User.groups}` resolves to the array of groups for the session.
# Combine with a USER-typed sid for catch-all attribute-based RLS:
#
#   {sid: {type: 'USER', principal: '*'},
#    filter: {field: 'partner_id', operator: 'IN', values: '${User.partner_id}'}}
#
# is the canonical "everyone sees only their own partner data" pattern.
# ----------------------------------------------------------------------


async def list_forced_filters(client: ComposerClient, source_id: str) -> list[dict]:
    """Return the source's current `forcedFilters` array."""
    src = await client.get(f"/sources/{source_id}")
    return src.get("forcedFilters") or []


def make_forced_filter(
    sid_type: str,
    sid_principal: str,
    field: str,
    operator: str = "EQUALS",
    values: list | str | None = None,
) -> dict:
    """Build a forced-filter entry of the standard shape.

    `values` may be a list of literals (`['DE', 'AT', 'CH']`) or a single
    string with attribute interpolation (`'${User.partner_id}'`).
    """
    return {
        "sid": {"type": sid_type.upper(), "principal": sid_principal},
        "filter": {
            "field": field,
            "operator": operator.upper(),
            "values": values if values is not None else [],
        },
    }


async def add_forced_filter(
    client: ComposerClient, source_id: str, forced_filter: dict
) -> dict:
    """Append a forced filter to a source. PUT-merges against existing
    filters — does not replace the array.
    """
    src = await client.get(f"/sources/{source_id}")
    existing = src.get("forcedFilters") or []
    existing.append(forced_filter)
    src["forcedFilters"] = existing
    return await client.put(f"/sources/{source_id}", src)


async def remove_forced_filters_for_sid(
    client: ComposerClient,
    source_id: str,
    sid_type: str,
    sid_principal: str,
) -> dict:
    """Drop every forced filter scoped to a given SID. Useful for cleanup
    when removing a tenant or rotating a group name.
    """
    src = await client.get(f"/sources/{source_id}")
    keep = []
    dropped = 0
    for ff in src.get("forcedFilters") or []:
        sid = ff.get("sid") or {}
        if (
            sid.get("type", "").upper() == sid_type.upper()
            and sid.get("principal") == sid_principal
        ):
            dropped += 1
        else:
            keep.append(ff)
    src["forcedFilters"] = keep
    if dropped:
        await client.put(f"/sources/{source_id}", src)
    return {"removed": dropped, "remaining": len(keep)}


async def clear_forced_filters(client: ComposerClient, source_id: str) -> dict:
    """Remove ALL forced filters from a source. Destructive — back up the
    array first via `list_forced_filters` if you want to restore."""
    src = await client.get(f"/sources/{source_id}")
    prev = src.get("forcedFilters") or []
    src["forcedFilters"] = []
    await client.put(f"/sources/{source_id}", src)
    return {"cleared": len(prev)}


# ----------------------------------------------------------------------
# Cross-warehouse introspection (multi-entity sources)
# ----------------------------------------------------------------------


async def describe_source_joins(client: ComposerClient, source_id: str) -> dict:
    """Summarise a source's join graph: entities, the connection each one
    comes from, and how they join.

    Returns:
      {
        "source": {"id", "name"},
        "entities": [{
          "id", "name",
          "connectionId", "schema", "collection",
          "fieldCount",
        }],
        "joins": [{
          "type", "from": {entity, fields}, "to": {entity, fields},
        }],
        "warehouses": [{"connectionId", "connectionName?", "entityIds"}],
      }
    """
    src = await client.get(f"/sources/{source_id}")
    entities_in = (src.get("storage") or {}).get("dataEntities") or []
    joins_in = (src.get("storage") or {}).get("joins") or []

    entities_out = []
    by_conn: dict[str, list[str]] = {}
    for e in entities_in:
        sc = e.get("singleCollection") or {}
        conn_id = sc.get("connectionId") or e.get("connectionId")
        entities_out.append({
            "id": e.get("id"),
            "name": e.get("name"),
            "connectionId": conn_id,
            "schema": sc.get("schema"),
            "collection": sc.get("collection"),
            "fieldCount": len(e.get("nativeFields") or []),
        })
        if conn_id:
            by_conn.setdefault(conn_id, []).append(e.get("id"))

    joins_out = []
    for j in joins_in:
        joins_out.append({
            "type": j.get("type") or j.get("joinType"),
            "from": {
                "entity": (j.get("from") or {}).get("entityId"),
                "fields": (j.get("from") or {}).get("fields"),
            },
            "to": {
                "entity": (j.get("to") or {}).get("entityId"),
                "fields": (j.get("to") or {}).get("fields"),
            },
        })

    # Resolve connection names where possible
    warehouses = []
    for conn_id, ents in by_conn.items():
        try:
            conn = await client.get(f"/connections/{conn_id}")
            conn_name = conn.get("name") or conn.get("connectionName")
            conn_type = conn.get("type") or conn.get("connectorType")
        except Exception:
            conn_name, conn_type = None, None
        warehouses.append({
            "connectionId": conn_id,
            "connectionName": conn_name,
            "connectionType": conn_type,
            "entityIds": ents,
        })

    return {
        "source": {"id": src.get("id"), "name": src.get("name")},
        "entities": entities_out,
        "joins": joins_out,
        "warehouses": warehouses,
        "isCrossWarehouse": len(warehouses) > 1,
    }


async def validate_source_field_uniqueness(
    client: ComposerClient, source_id: str
) -> dict:
    """Check whether every field on a multi-entity source is globally unique.
    Composer requires globally unique field names across entities; collisions
    cause silent fallback to default content at render time.

    Returns:
      {
        "ok": bool,
        "totalFields": int,
        "collisions": [{"name": "...", "entities": ["e1", "e2"]}],
      }
    """
    src = await client.get(f"/sources/{source_id}")
    seen: dict[str, list[str]] = {}
    for e in (src.get("storage") or {}).get("dataEntities") or []:
        eid = e.get("id")
        for f in e.get("nativeFields") or []:
            name = f.get("name")
            if not name:
                continue
            seen.setdefault(name, []).append(eid)
    collisions = [
        {"name": n, "entities": ents}
        for n, ents in seen.items()
        if len(ents) > 1
    ]
    return {
        "ok": not collisions,
        "totalFields": sum(len(v) for v in seen.values()),
        "collisions": collisions,
    }


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


async def list_uploads(client: ComposerClient) -> list[dict]:
    """List file-upload-backed datasets (`GET /uploads`).

    Composer can build a source from an uploaded file (CSV/Excel) instead of
    a live warehouse connection. This lists those uploads (id, name, size).
    Useful when scaffolding a demo from a flat file, and as the entry point
    for the writeback story documented in WRITEBACK_ODATA.md. Verified live
    against bundled Composer 26.2.0 (returns an empty list on a clean tenant).
    """
    items = await client.get_list("/uploads")
    return [
        {
            "id": u.get("id"),
            "name": u.get("name"),
            "description": u.get("description"),
            "fileSize": u.get("fileSize"),
            "accountId": u.get("accountId"),
        }
        for u in items
        if isinstance(u, dict)
    ]
