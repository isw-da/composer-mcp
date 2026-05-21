"""Embed-side orchestration helpers.

These tools sit on top of `tools.tokens` and are designed to make standing up
a parent-app embed (using the Composer Embed Manager `embed.js`) a one-call
operation rather than a hand-stitched flow.

Three primitives:

* `dashboard_id_for_embed(url_id)` — convert the `_`-separated dashboard id
  Composer uses in URLs to the `+`-separated form the embed manager wants.
* `verify_trusted_access_client(client_id, secret, account)` — probe whether
  a client is registered AND scoped to the target account by attempting a
  push-token mint and translating the error.
* `make_embed_config(...)` — mint a fresh push token and return a fully
  populated config dict you can paste straight into the shell file's
  `CONFIG = {...}` block.

Important: `make_embed_config` returns the trusted-access secret in its
output so the shell can re-mint tokens on each page load. That's fine for a
local-dev shell or a backend-relayed embed where the secret never leaves
your server. **Do not commit the output to a public repo.**
"""

from __future__ import annotations

from typing import Any

from ..client import ComposerClient
from . import tokens


def dashboard_id_for_embed(url_id: str) -> str:
    """Convert `<accountId>_<dashId>` (URL form) to `<accountId>+<dashId>`
    (embed manager form). Idempotent: passing the `+` form returns it
    unchanged.
    """
    if "+" in url_id:
        return url_id
    if "_" not in url_id:
        raise ValueError(
            "expected '<accountId>_<dashId>' or '<accountId>+<dashId>' format"
        )
    # Account UUIDs contain hyphens. Split on the FIRST underscore only.
    head, tail = url_id.split("_", 1)
    return f"{head}+{tail}"


async def verify_trusted_access_client(
    client: ComposerClient,
    client_id: str,
    secret: str,
    account: str,
    probe_username: str = "tenant.viewer",
) -> dict:
    """Sanity-check a Trusted Access client by attempting a push-token mint
    against the target account, and translate the result into something
    actionable.

    Returns one of:
      {ok: True, status: 200, account, expires_in, ...}
      {ok: False, reason: 'client_not_registered', status: 500, hint: '...'}
      {ok: False, reason: 'account_not_scoped', status: 400, hint: '...'}
      {ok: False, reason: 'user_not_in_account', status: 400, hint: '...'}
      {ok: False, reason: 'unknown', status: <code>, body: '...'}

    The push-token endpoint returns 500 'can't get authentication' when the
    client isn't registered, and 400 'invalid_request: account: <name> does
    not exist' when the client exists but isn't scoped to that account.
    Translating both into readable diagnostics saves a lot of debugging.
    """
    import base64
    import json
    import httpx

    url = client.cfg.base_url + client.cfg.context_path + "/api/trusted-access/push/tokens"
    auth_header = "Basic " + base64.b64encode(
        f"{client_id}:{secret}".encode()
    ).decode()
    headers = {
        "Accept": "application/vnd.composer.v3+json",
        "Content-Type": "application/vnd.composer.v3+json",
        "Authorization": auth_header,
    }
    body = {"username": probe_username, "account": account, "groups": []}

    async with httpx.AsyncClient(timeout=30.0) as h:
        resp = await h.post(url, json=body, headers=headers)

    if resp.status_code == 200:
        data = resp.json()
        return {
            "ok": True,
            "status": 200,
            "account": account,
            "expires_in": data.get("expires_in"),
            "token_type": data.get("token_type"),
        }

    text = resp.text
    if resp.status_code == 500 and "authentication" in text.lower():
        return {
            "ok": False,
            "reason": "client_not_registered",
            "status": 500,
            "hint": (
                "Trusted Access client {0} not registered on this Composer "
                "instance. Ask Symphony global admin to register it via "
                "POST /api/trusted-access/clients."
            ).format(client_id),
        }
    if resp.status_code == 400 and "does not exist" in text:
        return {
            "ok": False,
            "reason": "account_not_scoped",
            "status": 400,
            "hint": (
                "Client is registered but account {0!r} is not in its scope, "
                "OR the account name is wrong. The account field must be the "
                "literal display name with spaces and case, not a slug or UUID."
            ).format(account),
            "body": text[:300],
        }
    if resp.status_code == 400 and "user" in text.lower():
        return {
            "ok": False,
            "reason": "user_not_in_account",
            "status": 400,
            "hint": (
                "User {0!r} does not exist in account {1!r}. Pass an existing "
                "username via probe_username= or create the user."
            ).format(probe_username, account),
            "body": text[:300],
        }
    return {
        "ok": False,
        "reason": "unknown",
        "status": resp.status_code,
        "body": text[:500],
    }


async def make_embed_config(
    client: ComposerClient,
    client_id: str,
    secret: str,
    account: str,
    username: str,
    dashboard_ids: dict[str, str],
    groups: list[str] | None = None,
    theme: str = "__platform__",
    composer_api_url: str | None = None,
) -> dict:
    """Mint a push token and assemble a ready-to-paste config block for the
    Composer Embed Manager shell.

    `dashboard_ids` is a `{label: id}` map where each id can be in either
    URL form (`<accountId>_<dashId>`) or embed form (`<accountId>+<dashId>`).
    The output normalises to embed form.

    Returns a dict with the same shape as the `CONFIG = { ... }` block in
    `embed/partner-shell.html.template`:

      {
        "composerApiUrl": "...",
        "trustedAccess": {"clientId": ..., "secret": ...},
        "sharedUsername": ...,
        "account": ...,
        "group": <first of groups, or "" if none>,
        "theme": "__platform__",
        "dashboards": {label: "<accountId>+<dashId>", ...},
        "_token": {"access_token": ..., "expires_in": ..., "minted_at_iso": ...}
      }

    The `_token` block is included so callers that want to skip the
    client-side mint (and pass the token straight to `getToken()`) can do so.
    """
    import datetime as _dt

    base = composer_api_url or (client.cfg.base_url + client.cfg.context_path)
    tok = await tokens.mint_push_token(
        client, username=username, account=account, groups=groups
    )
    return {
        "composerApiUrl": base,
        "trustedAccess": {"clientId": client_id, "secret": secret},
        "sharedUsername": username,
        "account": account,
        "group": (groups or [""])[0],
        "groups": groups or [],
        "theme": theme,
        "dashboards": {
            label: dashboard_id_for_embed(did) for label, did in dashboard_ids.items()
        },
        "_token": {
            "access_token": tok.get("access_token"),
            "expires_in": tok.get("expires_in"),
            "token_type": tok.get("token_type"),
            "minted_at_iso": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        },
    }
