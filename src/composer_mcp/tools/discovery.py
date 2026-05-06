"""One-shot instance introspection — the meta-tool from the skill.

Run this before doing anything else against an unfamiliar instance. Returns
sources, fields, dashboards, accounts, connections in a single payload so
Claude can reason about what's available before generating config.
"""

from __future__ import annotations

from ..client import ComposerClient


async def introspect_instance(client: ComposerClient, max_sources: int = 10) -> dict:
    out: dict = {}

    # Current user / role
    try:
        out["user"] = await client.get("/user")
    except Exception as e:
        out["user"] = {"error": str(e)}

    # Connections
    try:
        conns = await client.get_list("/connections")
        out["connections"] = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "subStorageType": c.get("subStorageType"),
            }
            for c in conns
            if isinstance(c, dict)
        ]
    except Exception as e:
        out["connections"] = {"error": str(e)}

    # Sources + fields per source
    try:
        sources = await client.get_list("/sources")
        out["sources"] = []
        for s in sources[:max_sources]:
            if not isinstance(s, dict):
                continue
            entry = {
                "id": s.get("id"),
                "name": s.get("name"),
                "connectionId": s.get("connectionId"),
            }
            try:
                fields = await client.get_list(f"/sources/{s.get('id')}/fields")
                entry["fields"] = [
                    {"name": f.get("name"), "type": f.get("type") or f.get("dataType")}
                    for f in fields
                    if isinstance(f, dict)
                ]
            except Exception as e:
                entry["fields_error"] = str(e)
            out["sources"].append(entry)
    except Exception as e:
        out["sources"] = {"error": str(e)}

    # Dashboards
    try:
        dashboards = await client.get_list("/dashboards")
        out["dashboards"] = [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "widgetCount": len(
                    (d.get("dashboardLayout") or {}).get("layout", [])
                ),
            }
            for d in dashboards
            if isinstance(d, dict)
        ]
    except Exception as e:
        out["dashboards"] = {"error": str(e)}

    # Accounts
    try:
        accts = await client.get_list("/accounts")
        out["accounts"] = [
            {"id": a.get("id"), "name": a.get("name")}
            for a in accts
            if isinstance(a, dict)
        ]
    except Exception as e:
        out["accounts"] = {"error": str(e)}

    return out
