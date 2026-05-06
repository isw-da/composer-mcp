"""Multi-tenancy: accounts (tenants), user assignment, share dashboards."""

from __future__ import annotations

from ..client import ComposerClient


async def list_accounts(client: ComposerClient) -> list[dict]:
    items = await client.get_list("/accounts")
    return [
        {"id": a.get("id"), "name": a.get("name")}
        for a in items
        if isinstance(a, dict)
    ]


async def create_account(client: ComposerClient, name: str) -> dict:
    return await client.post("/accounts", {"name": name})


async def assign_users_to_account(
    client: ComposerClient, account_id: str, user_ids: list[str]
) -> dict:
    return await client.put(f"/accounts/{account_id}/users", user_ids)


async def share_dashboard(
    client: ComposerClient,
    dashboard_id: str,
    sids: list[dict],
    permission: str = "read",
) -> dict:
    """Share a dashboard with users / groups / accounts via ACL bulk update.
    sids: [{"type": "group", "name": "..."}] or {"type": "account", "name": "..."}
    """
    body = [{"sid": s, "permission": permission} for s in sids]
    return await client.put(f"/dashboards/{dashboard_id}/acls/bulk", body)
