"""Trusted access tokens for embedding.

Push tokens: caller specifies username, account, roles, attributes.
This is also the impersonation primitive — Otto's UC4 needs admins to
"replicate partner view" and push tokens give exactly that with full
forced-filter scoping applied.

Pull tokens: server-side user lookup, used when the embedding app already
has SSO context.
"""

from __future__ import annotations

from ..client import ComposerClient


async def mint_push_token(
    client: ComposerClient,
    username: str,
    account: str,
    roles: list[str],
    attributes: dict[str, list[str]] | None = None,
) -> dict:
    """Mint a push token impersonating a specific user.

    attributes uses array-of-string format for push tokens, e.g.
      {"partner_id": ["OTTO_PARTNER_007"]}
    Forced filters with ${User.partner_id} interpolation will receive
    the array values.
    """
    body = {
        "username": username,
        "account": account,
        "roles": roles or ["viewer"],
    }
    if attributes:
        body["attributes"] = attributes
    return await client.post("/trusted-access/push/tokens", body)


async def mint_pull_token(client: ComposerClient, username: str, account: str) -> dict:
    """Mint a pull token by looking up an existing user."""
    return await client.post(
        "/trusted-access/pull/tokens", {"username": username, "account": account}
    )
