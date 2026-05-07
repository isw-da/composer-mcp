#!/usr/bin/env python3
"""Dev server for the Otto-OPC embed shell.

Two responsibilities:

1. Serve the project directory on :8765 with aggressive no-cache headers
   so iterated shell edits land in the browser without manual cache
   clears or hard reloads. Composer's `embed.js` already caches visual
   configs against the push-token session (see LIMITATIONS.md), so the
   shell HTML cache is the last thing we want fighting iteration too.

2. Expose `POST /api/persona` — a per-persona forced-filter proxy.
   Takes `{partner_csv: "Otto Tech,Bergen Tech,..."}` and PUTs
   `source.filters` on every widget visual on the consolidated
   dashboard server-side. Empty CSV clears filters (Otto Admin →
   sees all partners).

   Why a proxy and not a browser-side mutation:
   * The PUT requires admin Basic Auth, which we don't expose to the
     browser.
   * Source-level Row Security on cross-warehouse joined sources 500s
     the data-engine pre-flight (see SAFETY.md and SCHEMA_NOTES.md).
     Per-visual `source.filters` PUT is the only API path that
     actually filters data at runtime. The shape Composer accepts is
     `{path, operation: "IN", value: [...]}` with singular `value`
     key — `values` plural is silently stripped to `path: null`.
   * `dashboard.rowFilters` is accepted and stored but ignored at
     runtime. `embed.js createComponent({filters})` is the filter
     pane visibility option, not data filtering. So per-visual is
     the only knob.

Set the four constants below for your tenant and you're done. Drop the
file into the project root, run `python3 serve_nocache.py`, point the
shell at `http://localhost:8765`.
"""

import http.server
import json
import os
import socketserver
import urllib.request
import base64
from urllib.error import HTTPError

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Composer admin creds + dashboard wiring ---
# Override these per environment. The credentials never leave the server;
# the browser sees only `/api/persona` as a same-origin POST.
COMPOSER_BASE = os.environ.get(
    "COMPOSER_BASE", "https://uat.logi-symphony.com/discovery"
)
ADMIN_USER    = os.environ.get("COMPOSER_ADMIN_USER", "admin")
ADMIN_PASS    = os.environ.get("COMPOSER_ADMIN_PASS", "<set-me>")

# IDs are tenant-specific — set them for your demo before running.
SOURCE_ID     = os.environ.get("COMPOSER_SOURCE_ID",    "<source-id>")
DASHBOARD_ID  = os.environ.get("COMPOSER_DASHBOARD_ID", "<dashboard-id>")
FILTER_PATH   = os.environ.get("COMPOSER_FILTER_PATH",  "partner_name")

_BASIC = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASS}".encode()).decode()
_API_HDRS = {
    "Authorization": f"Basic {_BASIC}",
    "Accept":        "application/vnd.composer.v3+json",
    "Content-Type":  "application/vnd.composer.v3+json",
}


def _api_get(path):
    req = urllib.request.Request(f"{COMPOSER_BASE}{path}", headers=_API_HDRS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _api_put(path, payload):
    req = urllib.request.Request(
        f"{COMPOSER_BASE}{path}",
        data=json.dumps(payload).encode(), method="PUT", headers=_API_HDRS,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def apply_persona_filter(partner_csv: str):
    """For every widget visual on the consolidated dashboard, write
    `source.filters = [{path: FILTER_PATH, operation: 'IN', value: [...]}]`
    (or `[]` to clear). Returns a summary dict."""
    dash = _api_get(f"/api/dashboards/{DASHBOARD_ID}")
    vids = []
    for w in dash.get("widgets", []):
        vid = w.get("visualId") or w.get("content", {}).get("visualId")
        if vid:
            vids.append(vid)

    values = [s.strip() for s in (partner_csv or "").split(",") if s.strip()]
    new_filter = (
        [{"path": FILTER_PATH, "operation": "IN", "value": values}]
        if values else []
    )

    updated, failed = [], []
    for vid in vids:
        try:
            v = _api_get(f"/api/visuals/{vid}")
            # Only act on visuals that use the configured source. Other
            # visuals (e.g. BigQuery direct comparisons) have their own
            # filter semantics and shouldn't be touched.
            if v.get("source", {}).get("sourceId") != SOURCE_ID:
                continue
            # Strip read-only fields before re-PUT.
            for k in ("createdByUserID", "createdDate", "creatingUserName",
                      "lastModifiedByUserID", "lastModifiedDate", "originId",
                      "version"):
                v.pop(k, None)
            v["source"]["filters"] = new_filter
            _api_put(f"/api/visuals/{vid}", v)
            updated.append(vid)
        except HTTPError as e:
            failed.append({"vid": vid, "code": e.code,
                           "body": e.read()[:200].decode("utf-8", "replace")})
        except Exception as e:
            failed.append({"vid": vid, "err": str(e)})

    return {"updated": updated, "failed": failed, "filter": new_filter}


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control",
                         "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma",  "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/persona":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw    = self.rfile.read(length) if length else b"{}"
                req    = json.loads(raw or b"{}")
                csv    = req.get("partner_csv", "")
                result = apply_persona_filter(csv)
                self._json(200, result)
            except HTTPError as e:
                self._json(e.code, {
                    "error": "composer_error", "code": e.code,
                    "body": e.read()[:400].decode("utf-8", "replace"),
                })
            except Exception as e:
                self._json(500, {"error": "proxy_error", "msg": str(e)})
            return
        self._json(404, {"error": "not_found"})


if __name__ == "__main__":
    os.chdir(ROOT)
    with socketserver.TCPServer(("", PORT), NoCacheHandler) as httpd:
        print(f"Serving {ROOT} at http://localhost:{PORT} (no-cache)")
        print("  POST /api/persona { \"partner_csv\": \"...\" }"
              " -> applies filter to all dashboard widgets")
        httpd.serve_forever()
