"""Trusted access tokens for embedding.

Push tokens: caller specifies username, account, groups, roles, attributes.
This is also the impersonation primitive — Otto's UC4 needs admins to
"replicate partner view" and push tokens give exactly that with full
forced-filter scoping applied.

Pull tokens: server-side user lookup, used when the embedding app already
has SSO context.

Schema notes (verified against UAT, Composer v25):

* `account` is the literal display name of the tenant, INCLUDING spaces.
  Example: `'Otto Group'`, not `'otto-group'` or the account UUID. Probing
  the slug returns `400 invalid_request: account: <slug> does not exist`
  even when the tenant is real.

* `groups` is the field the API actually reads for forced-filter group
  scoping. The older `roles` parameter still serialises but does nothing on
  recent builds. Pass groups when you want widget-level filters
  (e.g. `["TechWorld GmbH"]`).

* The Trusted Access *client* (clientId + secret used in the Basic Auth
  header) must be registered AND scoped to the target account by a
  Symphony global admin. Tenant admins cannot register clients themselves
  — `POST /api/trusted-access/clients` returns 403 from a tenant-admin
  session.

* Theme writes are also gated: `PUT /api/customization/themes/{id}` returns
  403 from amin's tenant-admin session, even for a theme that tenant
  created. Use `themes.list_themes` / `themes.get_theme` for the read side
  and ask Symphony ops for any palette changes.
"""

from __future__ import annotations

from ..client import ComposerClient


async def mint_push_token(
    client: ComposerClient,
    username: str,
    account: str,
    groups: list[str] | None = None,
    roles: list[str] | None = None,
    attributes: dict[str, list[str]] | None = None,
) -> dict:
    """Mint a push token impersonating a specific user.

    `account` is the tenant's display name verbatim (with spaces, mixed case).
    `groups` is the modern field the renderer uses for forced filter values
    e.g. `["TechWorld GmbH"]`. `roles` is kept for backwards compatibility.
    `attributes` uses array-of-string format, e.g. `{"partner_id": ["P_007"]}`.
    """
    body: dict = {"username": username, "account": account}
    if groups:
        body["groups"] = groups
    if roles:
        body["roles"] = roles
    if attributes:
        body["attributes"] = attributes
    return await client.post("/trusted-access/push/tokens", body)


async def mint_pull_token(client: ComposerClient, username: str, account: str) -> dict:
    """Mint a pull token by looking up an existing user."""
    return await client.post(
        "/trusted-access/pull/tokens", {"username": username, "account": account}
    )
