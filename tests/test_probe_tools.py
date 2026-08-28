"""Offline test: the two probe tools use endpoints that exist on 26.2.0.

Both were broken against the live build and both failed in the way that is
hardest to notice, by returning a confident answer.

`test_connection` called `POST /connections/{id}/test`, which does not exist
(404 on every method, and no connection+test path appears in the instance's own
api-docs). `test_dashboard_render` called `POST /visuals/{id}/data`, also
absent, so it marked every widget on every dashboard failed.

These assert the PATHS each tool requests, with a fake client, because the
defect was never in the parsing. A test that fed the tools a canned success
body would have passed throughout the entire period both were broken.

Run:  PYTHONPATH=src python3 -m tests.test_probe_tools
"""
import asyncio
import sys

from composer_mcp.client import ComposerError
from composer_mcp.tools import connections, dashboards

failures: list[str] = []


class FakeClient:
    """Records paths and returns whatever the case under test needs."""

    def __init__(self, responses: dict) -> None:
        self.responses = responses
        self.seen: list[tuple[str, str]] = []

    async def _dispatch(self, method: str, path: str):
        self.seen.append((method, path))
        r = self.responses.get(path, self.responses.get("*"))
        if isinstance(r, Exception):
            raise r
        return r

    async def get(self, path, **kw):
        return await self._dispatch("GET", path)

    async def post(self, path, json=None, **kw):
        return await self._dispatch("POST", path)

    async def request(self, method, path, json=None, params=None, **kw):
        return await self._dispatch(method, path)


def check(label: str, cond: bool, detail: str = "") -> None:
    if not cond:
        failures.append(f"{label}: {detail}")


async def main() -> None:
    # --- test_connection -------------------------------------------------
    c = FakeClient({"/connections/abc/schema": {"content": ["public", "sales"]}})
    r = await connections.test_connection(c, "abc")
    check("connection: path", ("GET", "/connections/abc/schema") in c.seen,
          f"asked for {c.seen}, not the schema endpoint that exists on 26.2.0")
    check("connection: ok", r["ok"] is True, f"got {r}")
    check("connection: evidence", r.get("schemas") == ["public", "sales"], f"got {r}")

    c = FakeClient({"*": ComposerError(404, "Not Found", {})})
    r = await connections.test_connection(c, "gone")
    check("connection: 404 is a clean no", r["ok"] is False and r["tested"] is True, f"got {r}")

    c = FakeClient({"*": ComposerError(500, "driver blew up", {})})
    r = await connections.test_connection(c, "broken")
    check("connection: db failure reported", r["ok"] is False and "did not answer" in r["reason"],
          f"got {r}")

    # the endpoint that does NOT exist must never be requested again
    c = FakeClient({"*": ComposerError(404, "Not Found", {})})
    await connections.test_connection(c, "x")
    check("connection: dead path not used",
          not any(p.endswith("/test") for _, p in c.seen),
          f"requested a /test path that 404s on this build: {c.seen}")

    # --- test_dashboard_render -------------------------------------------
    dash = {"id": "d1", "name": "D", "widgets": [{"id": "w1", "name": "w1", "visualId": "v1"}]}

    c = FakeClient({"/dashboards/d1": dash, "/visuals/v1": {"type": "BARS"},
                    "/export/visualdata/v1": {"rows": [1, 2, 3]}})
    r = await dashboards.test_dashboard_render(c, "d1")
    check("render: path", ("POST", "/export/visualdata/v1") in c.seen,
          f"asked for {c.seen}, not the export endpoint that exists on 26.2.0")
    check("render: rows pass", r["passed"] == 1 and r["failed"] == 0, f"got {r}")

    c = FakeClient({"/dashboards/d1": dash, "/visuals/v1": {"type": "BARS"},
                    "/export/visualdata/v1": {"rows": []}})
    r = await dashboards.test_dashboard_render(c, "d1")
    check("render: empty is a failure", r["failed"] == 1 and r["passed"] == 0,
          f"a visual returning no rows is the thing this tool exists to catch: {r}")

    # the case that must NOT be reported as a broken dashboard
    c = FakeClient({"/dashboards/d1": dash, "/visuals/v1": {"type": "BARS"},
                    "/export/visualdata/v1": ComposerError(
                        500, "Internal Server Error",
                        {"details": "Couldn't get an endpoint for service sdk-service"})})
    r = await dashboards.test_dashboard_render(c, "d1")
    check("render: absent export service is UNKNOWN",
          r.get("unknown") == 1 and r["failed"] == 0,
          f"a deployment without sdk-service must not condemn the dashboard: {r}")

    # a genuine server error is still a failure
    c = FakeClient({"/dashboards/d1": dash, "/visuals/v1": {"type": "BARS"},
                    "/export/visualdata/v1": ComposerError(500, "boom", {"details": "real fault"})})
    r = await dashboards.test_dashboard_render(c, "d1")
    check("render: other 500 still fails", r["failed"] == 1 and r.get("unknown") == 0, f"got {r}")

    for f in failures:
        print(f"FAIL  {f}")
    if failures:
        sys.exit(1)
    print("ok: both probe tools request endpoints that exist on 26.2.0, "
          "and an absent export service reads as unknown rather than as a broken dashboard")


if __name__ == "__main__":
    asyncio.run(main())
