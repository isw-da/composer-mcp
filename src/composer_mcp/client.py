"""
Composer API client — handles the vendor media type, base path, auth, CSRF,
and the wrapped-list response shape that the symphony-dashboard-builder-skill
documents as the most common gotchas.

Auth model (three flavours, in order of preference for unattended scripting):

  1. **Bearer token** (`COMPOSER_BEARER`): mint via /api/trusted-access/pull/tokens
     or /api/trusted-access/push/tokens. Stateless, works on both standalone
     and bundled Symphony, no CSRF needed. Recommended for production.

  2. **Basic Auth** (`COMPOSER_USER` + `COMPOSER_PASSWORD`): works on standalone
     Composer (mounted at /composer). On bundled Symphony (/discovery) Basic Auth
     against the v3 API is typically rejected as 401. Use only for local dev.

  3. **Session cookie + CSRF token** (`COMPOSER_SESSION_COOKIE` +
     `COMPOSER_CSRF_TOKEN`): bundled Symphony enforces Spring Security CSRF.
     Read the SESSION cookie value and the `<meta name="_csrf">` value from a
     logged-in browser tab and pass them via env vars. State-changing requests
     (POST/PUT/DELETE/PATCH) get the CSRF header automatically.

Key invariants enforced here:
  - Content-Type and Accept are always application/vnd.composer.v3+json.
  - Base path is `{host}{context_path}/api/...` where context_path is
    `/composer` (standalone) or `/discovery` (SI/Symphony bundle).
  - List responses are unwrapped from {content: [...]} when present.
  - X-CSRF-TOKEN is added to mutation requests when the env var is set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

VENDOR_MEDIA_TYPE = "application/vnd.composer.v3+json"


class ComposerError(RuntimeError):
    def __init__(self, status: int, message: str, body: Any = None) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.body = body


_MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Hard guardrails added 2026-05-07 after locking admin.synced out of the
# instance by mutating his own user record via the trusted-access push token.
# See SAFETY.md at the repo root for the full incident.

# 1) Refuse to mutate /api/users/{id} when {id} matches the running
#    session's userId. The legitimate use case (a user editing their
#    own profile via the UI) goes through different surface area; the
#    MCP doesn't need to support self-mutation by ID.
_USER_ID_PATH_RE = None  # lazily compiled below

# 2) Refuse calls into /managed/* (MDR module). Per the post-incident
#    rule: composer-mcp lives in the VDD/discovery world only. If you
#    need to push something through MDR you do it manually, deliberately,
#    outside this codebase.
_MDR_PATH_PREFIXES = ("/managed", "managed/")


class MdrEndpointBlocked(RuntimeError):
    """Raised when something tries to call a /managed/* (MDR) endpoint.

    Per the 2026-05-07 incident: composer-mcp is VDD-only. MDR endpoints
    are a footgun (see SAFETY.md, the June 2025 warning email) and we
    don't drive them from automation. If you genuinely need MDR, do it
    manually with a fresh CLI / curl + a documented one-shot session.
    """


class SelfUserMutationBlocked(RuntimeError):
    """Raised when a write would mutate the running session's own user record.

    Specifically: PUT/PATCH/DELETE on `/api/users/{runningUserId}`. This is
    how admin.synced locked himself out on 2026-05-07.
    """


@dataclass(frozen=True)
class ComposerConfig:
    base_url: str                 # e.g. http://localhost:18080
    context_path: str             # /composer (standalone) or /discovery (SI/Symphony bundle)
    user: str                     # e.g. admin
    password: str                 # admin password
    bearer: str | None = None     # if set, used instead of Basic
    session_cookie: str | None = None  # Spring Security SESSION cookie value (bundled Symphony)
    csrf_token: str | None = None      # Spring Security CSRF token (bundled Symphony)

    @classmethod
    def from_env(cls) -> "ComposerConfig":
        base = os.environ.get("COMPOSER_BASE", "http://localhost:18080")
        # Standalone Composer mounts at /composer; SI/Symphony-bundled Composer at /discovery.
        context = os.environ.get("COMPOSER_CONTEXT_PATH", "/composer")
        user = os.environ.get("COMPOSER_USER", "admin")
        password = os.environ.get("COMPOSER_PASSWORD", "")
        bearer = os.environ.get("COMPOSER_BEARER")
        session_cookie = os.environ.get("COMPOSER_SESSION_COOKIE")
        csrf_token = os.environ.get("COMPOSER_CSRF_TOKEN")
        if not password and not bearer and not session_cookie:
            raise RuntimeError(
                "Set one of: COMPOSER_PASSWORD, COMPOSER_BEARER, "
                "or COMPOSER_SESSION_COOKIE (+ COMPOSER_CSRF_TOKEN for bundled Symphony) "
                "before starting the server"
            )
        if session_cookie and not csrf_token:
            # Not a hard error: GETs work without it. Mutations will 403 until CSRF is set.
            pass
        if not context.startswith("/"):
            context = "/" + context
        return cls(
            base.rstrip("/"),
            context.rstrip("/"),
            user,
            password,
            bearer,
            session_cookie,
            csrf_token,
        )


class ComposerClient:
    """Thin httpx wrapper that knows Composer's quirks."""

    def __init__(self, cfg: ComposerConfig) -> None:
        self.cfg = cfg
        headers = {
            "Accept": VENDOR_MEDIA_TYPE,
            "Content-Type": VENDOR_MEDIA_TYPE,
        }
        cookies: dict[str, str] = {}
        auth = None
        if cfg.bearer:
            headers["Authorization"] = f"Bearer {cfg.bearer}"
        elif cfg.session_cookie:
            # Bundled Symphony login flow: Spring Security session cookie.
            # SESSION is the canonical cookie name on /discovery; /managed
            # may set additional cookies, but SESSION is what /api/* honours.
            cookies["SESSION"] = cfg.session_cookie
        else:
            auth = (cfg.user, cfg.password)
        self._client = httpx.AsyncClient(
            base_url=cfg.base_url + cfg.context_path,
            headers=headers,
            auth=auth,
            cookies=cookies or None,
            timeout=httpx.Timeout(60.0),
            follow_redirects=False,
        )
        # Cache of the running session's user id, populated lazily on the
        # first request. Used by the self-mutation guard.
        self._running_user_id: str | None = None
        self._running_user_id_fetched: bool = False

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _unwrap(data: Any) -> Any:
        """Composer list endpoints return {content: [...]} sometimes, raw list other times."""
        if isinstance(data, dict):
            for key in ("content", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return data

    def _mutation_headers(self, method: str) -> dict[str, str]:
        """Return any per-request headers that depend on the HTTP method.

        Bundled Symphony (Spring Security) requires `X-CSRF-TOKEN` on every
        state-changing request. Without it, the API returns 403 with the
        misleading message "Your user session has expired. Please refresh
        the page to get a new user session established before changes can
        be saved." That's not a session expiry — it's the CSRF gate.
        """
        headers: dict[str, str] = {}
        if method.upper() in _MUTATING_METHODS and self.cfg.csrf_token:
            headers["X-CSRF-TOKEN"] = self.cfg.csrf_token
        return headers

    async def _ensure_running_user_id(self) -> str | None:
        """Fetch and cache the running session's user id (best-effort)."""
        if self._running_user_id_fetched:
            return self._running_user_id
        self._running_user_id_fetched = True
        try:
            resp = await self._client.request("GET", "/api/user")
            if resp.status_code < 400 and resp.content:
                body = resp.json()
                if isinstance(body, dict):
                    self._running_user_id = body.get("id") or body.get("userId")
        except Exception:
            self._running_user_id = None
        return self._running_user_id

    async def _enforce_guards(self, method: str, path: str) -> None:
        """Hard guards. See module docstring + SAFETY.md."""
        # Guard 1: never call /managed/* (MDR module). composer-mcp is VDD-only.
        # Strip leading slash for prefix check.
        check_path = path if path.startswith("/") else "/" + path
        if any(check_path.startswith(p) for p in _MDR_PATH_PREFIXES):
            raise MdrEndpointBlocked(
                f"Refusing to call MDR endpoint '{path}'. composer-mcp is "
                f"VDD-only by policy after the 2026-05-07 incident. If you "
                f"need MDR, do it manually outside this codebase."
            )

        # Guard 2: refuse to mutate /api/users/{me} for the running session.
        if method.upper() in {"PUT", "PATCH", "DELETE"}:
            # /api/users/{id} or /users/{id}
            import re
            m = re.match(r"^/?(?:api/)?users/([^/?#]+)/?$", check_path.lstrip("/"))
            if m:
                target_id = m.group(1)
                me = await self._ensure_running_user_id()
                if me and target_id == me:
                    raise SelfUserMutationBlocked(
                        f"Refusing {method} on /api/users/{target_id} because "
                        f"that is the running session's own user id. This is "
                        f"how admin.synced locked himself out on 2026-05-07. "
                        f"See SAFETY.md."
                    )

    async def request(
        self, method: str, path: str, json: Any | None = None, params: dict | None = None
    ) -> Any:
        path = path if path.startswith("/") else "/" + path
        path = path if path.startswith("/api") else "/api" + path
        await self._enforce_guards(method, path)
        extra_headers = self._mutation_headers(method)
        resp = await self._client.request(
            method, path, json=json, params=params, headers=extra_headers or None
        )
        if resp.status_code >= 400:
            try:
                body = resp.json()
                msg = body.get("message") or body.get("error") or resp.text[:200]
            except Exception:
                body = resp.text[:500]
                msg = body
            raise ComposerError(resp.status_code, msg, body)
        if not resp.content:
            return None
        try:
            return resp.json()
        except Exception:
            return resp.text

    async def get(self, path: str, **kw) -> Any:
        return await self.request("GET", path, **kw)

    async def get_list(self, path: str, **kw) -> list[Any]:
        return self._unwrap(await self.get(path, **kw))

    async def post(self, path: str, json: Any | None = None, params: dict | None = None) -> Any:
        return await self.request("POST", path, json=json, params=params)

    async def put(self, path: str, json: Any | None = None, params: dict | None = None) -> Any:
        return await self.request("PUT", path, json=json, params=params)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)
