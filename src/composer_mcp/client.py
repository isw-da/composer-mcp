"""
Composer API client — handles the vendor media type, base path, auth, and
the wrapped-list response shape that the symphony-dashboard-builder-skill
documents as the most common gotchas.

Auth model:
  - Basic Auth (admin:password) is used for routine GET/POST as a development
    fallback.
  - For production embedding we'd mint a Bearer token via the
    /api/trusted-access/push/tokens endpoint and use that. Bearer support is
    in here but most tools default to Basic against a local instance.

Key invariants enforced here:
  - Content-Type and Accept are always application/vnd.composer.v3+json.
  - Base path is always {host}/discovery/api/...
  - List responses are unwrapped from {content: [...]} when present.
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


@dataclass(frozen=True)
class ComposerConfig:
    base_url: str        # e.g. http://localhost:18080
    context_path: str    # e.g. /composer (standalone) or /discovery (SI bundle)
    user: str            # e.g. admin
    password: str        # admin password
    bearer: str | None = None  # if set, used instead of Basic

    @classmethod
    def from_env(cls) -> "ComposerConfig":
        base = os.environ.get("COMPOSER_BASE", "http://localhost:18080")
        # Standalone Composer mounts at /composer; SI-bundled Composer at /discovery.
        context = os.environ.get("COMPOSER_CONTEXT_PATH", "/composer")
        user = os.environ.get("COMPOSER_USER", "admin")
        password = os.environ.get("COMPOSER_PASSWORD", "")
        bearer = os.environ.get("COMPOSER_BEARER")
        if not password and not bearer:
            raise RuntimeError(
                "Set COMPOSER_PASSWORD (or COMPOSER_BEARER) before starting the server"
            )
        if not context.startswith("/"):
            context = "/" + context
        return cls(base.rstrip("/"), context.rstrip("/"), user, password, bearer)


class ComposerClient:
    """Thin httpx wrapper that knows Composer's quirks."""

    def __init__(self, cfg: ComposerConfig) -> None:
        self.cfg = cfg
        headers = {
            "Accept": VENDOR_MEDIA_TYPE,
            "Content-Type": VENDOR_MEDIA_TYPE,
        }
        if cfg.bearer:
            headers["Authorization"] = f"Bearer {cfg.bearer}"
            auth = None
        else:
            auth = (cfg.user, cfg.password)
        self._client = httpx.AsyncClient(
            base_url=cfg.base_url + cfg.context_path,
            headers=headers,
            auth=auth,
            timeout=httpx.Timeout(60.0),
            follow_redirects=False,
        )

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

    async def request(
        self, method: str, path: str, json: Any | None = None, params: dict | None = None
    ) -> Any:
        path = path if path.startswith("/") else "/" + path
        path = path if path.startswith("/api") else "/api" + path
        resp = await self._client.request(method, path, json=json, params=params)
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

    async def post(self, path: str, json: Any) -> Any:
        return await self.request("POST", path, json=json)

    async def put(self, path: str, json: Any) -> Any:
        return await self.request("PUT", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)
