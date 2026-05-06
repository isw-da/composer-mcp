"""Smoke test — runs introspect_instance directly against the configured Composer.

Run via:
  COMPOSER_BASE=http://localhost:18080 \
  COMPOSER_USER=admin \
  COMPOSER_PASSWORD=... \
  .venv/bin/python -m tests.smoke
"""

import asyncio
import json

from composer_mcp.client import ComposerClient, ComposerConfig
from composer_mcp.tools.discovery import introspect_instance


async def main() -> None:
    cfg = ComposerConfig.from_env()
    print(f"Base: {cfg.base_url}")
    print(f"User: {cfg.user}")
    client = ComposerClient(cfg)
    try:
        out = await introspect_instance(client, max_sources=5)
    finally:
        await client.aclose()
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
