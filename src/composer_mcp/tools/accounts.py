"""Multi-tenancy: accounts (tenants), user/admin assignment, tenant switching,
dashboard sharing.

⚠️  PUT-REPLACE WARNING — READ SAFETY.md BEFORE CALLING ANY MUTATION HERE. ⚠️

Every PUT in this module REPLACES the entire collection on the server. If
you call `add_users_to_account` with a list of one user, you have evicted
every other user from that tenant. Same shape applies to `add_admins_to_account`
and the dashboard ACL bulk update. Always read first, modify the list in
memory, then write back the full list.

This is the same class of bug that wiped amin.hasan's VDD admin roles
on 2026-05-07 (different endpoint, same root cause: not enforcing
read-modify-write on overwrite-style endpoints). See SAFETY.md.

Lessons from real bundled-Symphony usage:

* `POST /api/accounts` does NOT accept `{name}` directly. The endpoint expects
  an `AccountUserResource` shape: `{account: {name, disabled}, users: []}`.
  The earlier MCP version got this wrong and produced 400s on bundled Symphony.

* Adding users to a tenant uses `PUT` (not `POST`) and the body is a flat
  array of `{id, name}` (NOT wrapped in `{users:[...]}`). Same for `/admins`.
  The PUT REPLACES the existing list — to add a user, include the existing
  members plus the new one.

* A user must already be a member of the tenant before being promoted to
  admin. Sending only the admin add returns 400 with "User X doesn't belong
  to account Y".

* Cross-tenant user moves are gated. amin's `ROLE_ADMINISTER_USERS` within
  Otto is sufficient to add amin himself, but is NOT sufficient to import a
  user record that belongs to a different tenant. That requires a
  Symphony-wide super-admin (Global Administrator). Global users like Peter
  Armstrong already have implicit access to every tenant and don't need to
  be added explicitly.

* `GET /api/user/switch/{accountId}` switches the active tenant context for
  the calling session. Subsequent /api/* calls run in that tenant's scope
  until the next switch. Page reloads reset to the user's primary tenant.
"""

from __future__ import annotations

from ..client import ComposerClient


async def list_accounts(client: ComposerClient) -> list[dict]:
    items = await client.get_list("/accounts")
    return [
        {
            "id": a.get("id"),
            "name": a.get("name"),
            "disabled": a.get("disabled", False),
            "numberOfUsers": a.get("numberOfUsers"),
        }
        for a in items
        if isinstance(a, dict)
    ]


async def create_account(
    client: ComposerClient, name: str, users: list[dict] | None = None
) -> dict:
    """Create a new tenant.

    Body shape is `AccountUserResource`: `{account: {...}, users: [...]}`.
    Pass `users=[{id, name}, ...]` to attach existing users in the same call,
    or omit and add them later via `add_users_to_account`.
    """
    body = {
        "account": {"name": name, "disabled": False},
        "users": users or [],
    }
    return await client.post("/accounts", body)


async def get_account_users(client: ComposerClient, account_id: str) -> list[dict]:
    """List the users currently assigned to a tenant."""
    return await client.get_list(f"/accounts/{account_id}/users")


async def get_account_admins(client: ComposerClient, account_id: str) -> list[dict]:
    """List the admins of a tenant."""
    return await client.get_list(f"/accounts/{account_id}/admins")


async def add_users_to_account(
    client: ComposerClient, account_id: str, users: list[dict]
) -> dict:
    """Replace the user list of a tenant.

    `users` is a flat list of `{id, name}` objects. PUT REPLACES — fetch the
    existing list with `get_account_users` and append before calling, otherwise
    you'll evict everyone except the users you pass.
    """
    return await client.put(f"/accounts/{account_id}/users", users)


async def add_admins_to_account(
    client: ComposerClient, account_id: str, users: list[dict]
) -> dict:
    """Replace the admin list of a tenant.

    Each user in the list must already be a member (use `add_users_to_account`
    first). Same PUT-replace semantics as users.
    """
    return await client.put(f"/accounts/{account_id}/admins", users)


async def switch_tenant(client: ComposerClient, account_id: str) -> dict:
    """Switch the active tenant context for the current session.

    Until the next switch (or page reload in a browser session), all `/api/*`
    calls run in this tenant's scope: list_sources / list_dashboards /
    list_connections all return only the tenant's own records.

    Idempotent: switching to a tenant the user already has active is a no-op.
    Returns 200 + empty body on success, 400 with "Can't set active account
    for X to Y" if the user is not a member of the target tenant.
    """
    await client.get(f"/user/switch/{account_id}")
    return {"switched_to": account_id}


# --- assignment alias kept for backward compatibility ---


async def assign_users_to_account(
    client: ComposerClient, account_id: str, user_ids: list[str]
) -> dict:
    """Deprecated: shape changed to `[{id, name}, ...]`. Use add_users_to_account."""
    users = [{"id": uid, "name": uid} for uid in user_ids]
    return await add_users_to_account(client, account_id, users)


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
