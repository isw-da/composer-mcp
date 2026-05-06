"""Source (semantic-layer) management.

A "source" in Composer is a queryable object built on top of a connection,
exposing a set of fields with friendly names and types. Visuals reference
source IDs, not raw tables.
"""

from __future__ import annotations

from ..client import ComposerClient


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


async def create_source(
    client: ComposerClient,
    name: str,
    connection_id: str,
    schema: str,
    table: str,
    description: str = "",
) -> dict:
    """Create a new data source against a single table or view in a connection.

    Uses the v2 API which is cleaner than v1 — caller specifies the entity at
    the top level rather than nested in a storage.dataEntities[] block.
    Composer auto-introspects fields from the underlying connection's schema.

    For multi-entity sources with joins, use create_source_v2 directly with
    the full V2 body shape.
    """
    body = {
        "name": name,
        "description": description,
        "entities": [
            {
                "name": table,
                "connectionId": connection_id,
                "schema": schema,
                "collection": table,
            }
        ],
    }
    return await client.post("/v2/sources", body)


async def create_source_v2(client: ComposerClient, body: dict) -> dict:
    """Create a source with a full V2 body (multiple entities, joins, etc).

    See https://localhost:18080/composer/api-docs SourceV2Resource schema.
    """
    return await client.post("/v2/sources", body)


async def delete_source(client: ComposerClient, source_id: str) -> dict:
    await client.delete(f"/sources/{source_id}")
    return {"deleted": source_id}
