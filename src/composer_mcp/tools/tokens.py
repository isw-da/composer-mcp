"""Trusted access tokens for embedding.

⚠️  DANGER LANE — READ THIS BEFORE TOUCHING.  ⚠️

The trusted-access PUSH endpoint is a CREATE-OR-OVERWRITE primitive.
On every call it writes a full user record server-side, replacing whatever
was there. **Any field you don't set gets cleared.** Glyn McKenna's June
email spelled this out and warned against using it inside Logi Symphony
because it bypasses MDR (the source of truth) and silently desyncs the
user from the Symphony admin's view.

What this means in practice:

* Pushing a token for the user the script is RUNNING AS will overwrite
  that user's groups + roles + custom attributes with the (likely
  partial) payload you send. Worst case: you strip your own admin and
  lock yourself out of the platform. (This happened to amin.hasan on
  2026-05-07. Took an admin restore from Leo to recover.)

* The `roles` parameter is silently ignored on token issuance but still
  participates in the overwrite. We removed it from this wrapper; do not
  re-add it.

* For provisioning users INSIDE Logi Symphony, prefer MDR's long-form
  `/managed/API/Logon` with `accountProperties`. That writes via the
  source of truth and syncs to VDD automatically.

Use push tokens for:
  - Per-render impersonation of EPHEMERAL users (demo personas, viewers
    that exist only at the API tier).

Do NOT use push tokens for:
  - Mutating real users that exist in the admin UI.
  - Adding/removing groups on yourself or any teammate.
  - "Quick fixes" of broken user records — you'll just break them more.

Pull tokens: server-side user lookup, used when the embedding app already
has SSO context. Read-only — safe to call against any existing user.

Schema notes (verified against UAT, Composer v25):

* `account` is the literal display name of the tenant, INCLUDING spaces.
  Example: `'Otto Group'`, not `'otto-group'` or the account UUID. Probing
  the slug returns `400 invalid_request: account: <slug> does not exist`
  even when the tenant is real.

* `groups` is the field the API actually reads for forced-filter group
  scoping. Pass groups when you want widget-level filters
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


class SelfMutationBlocked(RuntimeError):
    """Raised when a write would overwrite the running session's own user record.

    This is the safety guard Amin earned the hard way on 2026-05-07.
    See the module docstring above and SAFETY.md.
    """


async def _running_session_username(client: ComposerClient) -> str | None:
    """Best-effort fetch of the username the current session is authenticated as.
    Returns None if the lookup fails (e.g. unauthenticated, network error)."""
    try:
        me = await client.get("/user")
        if isinstance(me, dict):
            return me.get("name")
    except Exception:
        return None
    return None


async def mint_push_token(
    client: ComposerClient,
    username: str,
    account: str,
    groups: list[str] | None = None,
    attributes: dict[str, list[str]] | None = None,
    *,
    allow_self: bool = False,
) -> dict:
    """Mint a push token impersonating a specific user.

    ⚠️  This is a CREATE-OR-OVERWRITE call. Read the module docstring before
    using on any user that exists in the admin UI.

    Args:
      username: target user. **Must not equal the running session's username**
                unless `allow_self=True` is passed explicitly. Self-overwrites
                have wiped admin roles in the past.
      account:  tenant display name verbatim (with spaces, mixed case).
      groups:   forced-filter groups, e.g. `["TechWorld GmbH"]`.
      attributes: array-of-string format, e.g. `{"partner_id": ["P_007"]}`.
      allow_self: opt-in escape hatch. Only set this if you have explicitly
                  reasoned through the risk and the call is part of a
                  full-payload restore (not a partial mutation).

    The `roles` parameter has been removed deliberately. The Composer server
    silently ignores it on issuance but still participates in the overwrite,
    which is how amin.hasan lost their admin roles in May 2026. If you think
    you need roles, you almost certainly want MDR's `/managed/API/Logon` with
    `accountProperties.groupMembership` instead.
    """
    if not allow_self:
        running_user = await _running_session_username(client)
        if running_user and running_user.lower() == (username or "").lower():
            raise SelfMutationBlocked(
                f"Refusing to mint a push token for '{username}' because that "
                f"is the running session's own user. This call would overwrite "
                f"your own roles/groups/attributes server-side, which is "
                f"how amin.hasan locked themselves out on 2026-05-07. "
                f"If you genuinely need this (full-payload restore from a "
                f"trusted backup), pass `allow_self=True` and own the risk."
            )

    body: dict = {"username": username, "account": account}
    if groups:
        body["groups"] = groups
    if attributes:
        body["attributes"] = attributes
    return await client.post("/trusted-access/push/tokens", body)


async def mint_pull_token(client: ComposerClient, username: str, account: str) -> dict:
    """Mint a pull token by looking up an existing user.

    Read-only on the server side: this does not mutate the user record.
    Safe to call against any existing user including yourself.
    """
    return await client.post(
        "/trusted-access/pull/tokens", {"username": username, "account": account}
    )
