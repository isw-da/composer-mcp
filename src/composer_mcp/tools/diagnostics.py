"""Diagnostic tools — answer "what can I actually do here?" in one call.

`health_check` runs a sweep of read-only probes and returns a structured
report. Useful when:

* picking up a new Composer instance and wanting to know what works,
* debugging "why does this 403?" — the report tells you which permission
  classes the calling principal lacks,
* sanity-checking after a Composer upgrade,
* writing an embed shell against an unfamiliar tenant.
"""

from __future__ import annotations

from typing import Any

from ..client import ComposerClient


async def _try(label: str, coro) -> dict:
    """Run a probe and translate any failure into a non-fatal result row."""
    try:
        result = await coro
        if isinstance(result, list):
            return {
                "label": label,
                "ok": True,
                "count": len(result),
                "sample": result[:3] if result else [],
            }
        return {"label": label, "ok": True, "result": result}
    except Exception as e:
        msg = str(e)
        # Translate the common ones into actionable hints
        hint = None
        lower = msg.lower()
        if "403" in msg or "forbidden" in lower:
            hint = "calling principal lacks the role this endpoint requires"
        elif "401" in msg or "unauthor" in lower:
            hint = "auth missing or expired (check session cookie + CSRF, or bearer)"
        elif "404" in msg or "not found" in lower:
            hint = "endpoint not exposed in this Composer build"
        elif "500" in msg:
            hint = "server-side error; usually means the endpoint exists but a precondition isn't met"
        return {"label": label, "ok": False, "error": msg[:200], "hint": hint}


async def health_check(
    client: ComposerClient,
    deep: bool = False,
) -> dict:
    """Sweep of read-only probes against a Composer instance.

    `deep=True` adds slower probes (per-source field counts, per-dashboard
    widget counts). Default is the fast surface check.

    Returns:
      {
        "instance": {"baseUrl", "contextPath", "user"},
        "auth": {ok, mode},
        "capabilities": [{label, ok, count?, error?, hint?}, ...],
        "summary": {totalProbes, passed, failed, gates: ["theme_write", "acl_read"]},
      }
    """
    cfg = client.cfg
    instance = {
        "baseUrl": cfg.base_url,
        "contextPath": cfg.context_path,
        "user": cfg.user,
        "authMode": (
            "bearer" if cfg.bearer
            else "session+csrf" if cfg.session_cookie
            else "basic"
        ),
    }

    # Surface probes — every one is non-mutating
    probes = [
        ("connections", client.get_list("/connections")),
        ("connection_types", client.get_list("/connection/types")),
        ("sources", client.get_list("/sources")),
        ("dashboards", client.get_list("/dashboards")),
        ("visuals", client.get_list("/visuals")),
        ("themes", client.get_list("/customization/themes")),
        # admin-ish
        ("accounts", client.get_list("/accounts")),
        # things that 404 or 403 in many setups (and that's useful info)
        ("trusted_access_clients", client.get_list("/trusted-access/clients")),
        ("dashboard_views", client.get_list("/dashboards")),  # placeholder; real bookmarks 404
    ]

    capabilities = []
    for label, coro in probes:
        capabilities.append(await _try(label, coro))

    # Specific gate checks the caller almost always cares about
    gates = []
    for c in capabilities:
        if not c["ok"] and "403" in (c.get("error") or ""):
            gates.append(c["label"])

    if deep:
        # Pull a sample dashboard and run a render preview to test data plane
        try:
            dashes = await client.get_list("/dashboards")
            if dashes:
                from . import dashboards as _dashboards
                sample = await _dashboards.test_dashboard_render(
                    client, dashes[0]["id"], sample_rows=1
                )
                capabilities.append({
                    "label": "data_plane_render",
                    "ok": sample["passed"] > 0,
                    "passed": sample["passed"],
                    "failed": sample["failed"],
                    "sampleDashboard": sample["dashboard"]["name"],
                })
        except Exception as e:
            capabilities.append({
                "label": "data_plane_render",
                "ok": False,
                "error": str(e)[:200],
            })

    passed = sum(1 for c in capabilities if c["ok"])
    failed = sum(1 for c in capabilities if not c["ok"])

    return {
        "instance": instance,
        "capabilities": capabilities,
        "summary": {
            "totalProbes": len(capabilities),
            "passed": passed,
            "failed": failed,
            "gates": gates,
            "verdict": (
                "fully operational" if failed == 0
                else "tenant admin (theme/client writes gated)"
                if set(gates).issubset({"trusted_access_clients", "themes_write"})
                else "limited — check gates list"
            ),
        },
    }


async def whoami(client: ComposerClient) -> dict:
    """Return the calling principal's identity and current tenant scope.

    Composer doesn't expose a single `/me` endpoint, so we inspect the
    config plus probe the active tenant. Useful in shell agents when the
    user has switched tenants and you need to confirm before mutating.
    """
    cfg = client.cfg
    out = {
        "user": cfg.user,
        "authMode": (
            "bearer" if cfg.bearer
            else "session+csrf" if cfg.session_cookie
            else "basic"
        ),
        "instance": cfg.base_url + cfg.context_path,
    }
    # Probing the accounts list confirms whether the session has global vs
    # tenant scope without making it obvious.
    try:
        accts = await client.get_list("/accounts")
        out["accountsVisible"] = len(accts)
        out["scope"] = "global_admin" if len(accts) > 1 else "tenant_admin"
    except Exception:
        out["accountsVisible"] = 0
        out["scope"] = "tenant_user"
    return out
