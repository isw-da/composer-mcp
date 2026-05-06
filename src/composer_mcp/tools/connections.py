"""Connection management — data warehouse / database connections."""

from __future__ import annotations

from typing import Any
from ..client import ComposerClient


async def list_connection_types(client: ComposerClient) -> list[dict]:
    """Return the connector types registered with this Composer instance.
    Each item has id, name, subStorageType.
    """
    items = await client.get_list("/connection/types")
    return [
        {
            "id": c["id"],
            "name": c.get("name"),
            "subStorageType": c.get("subStorageType"),
        }
        for c in items
        if isinstance(c, dict)
    ]


async def get_connection_type(client: ComposerClient, type_id: str) -> dict:
    """Get full schema (parameters list) for a connector type.
    Useful before creating a connection to know which params are required.
    """
    return await client.get(f"/connection/types/{type_id}")


async def list_connections(client: ComposerClient) -> list[dict]:
    """List all data connections in the instance."""
    items = await client.get_list("/connections")
    return [
        {
            "id": c["id"],
            "name": c.get("name"),
            "subStorageType": c.get("subStorageType"),
            "connectionTypeId": c.get("connectionTypeId"),
            "disabled": c.get("disabled", False),
        }
        for c in items
        if isinstance(c, dict)
    ]


async def get_connection(client: ComposerClient, connection_id: str) -> dict:
    """Get full connection details (parameters with passwords masked)."""
    return await client.get(f"/connections/{connection_id}")


async def create_connection(
    client: ComposerClient,
    name: str,
    connection_type_id: str,
    sub_storage_type: str,
    parameters: dict[str, str],
) -> dict:
    """Create a new data connection.
    parameters maps API param keys to values, e.g.
      {"JDBC_URL": "...", "USER_NAME": "...", "PASSWORD": "..."}
    See get_connection_type to discover required params per connector type.
    """
    body = {
        "name": name,
        "type": "EDC2",
        "connectionTypeId": connection_type_id,
        "subStorageType": sub_storage_type,
        "allParameters": [
            {"key": k, "value": v, "systemAccess": False}
            for k, v in parameters.items()
        ],
    }
    return await client.post("/connections", body)


async def delete_connection(client: ComposerClient, connection_id: str) -> dict:
    await client.delete(f"/connections/{connection_id}")
    return {"deleted": connection_id}
