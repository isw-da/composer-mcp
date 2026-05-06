#!/usr/bin/env python3
"""Serves the otto-composer directory on :8765 with aggressive no-cache headers
so iterated shell edits show up immediately in the browser without manual cache
clears or hard reloads."""

import http.server
import socketserver
import os

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


if __name__ == "__main__":
    os.chdir(ROOT)
    with socketserver.TCPServer(("", PORT), NoCacheHandler) as httpd:
        print(f"Serving {ROOT} at http://localhost:{PORT} (no-cache)")
        httpd.serve_forever()
