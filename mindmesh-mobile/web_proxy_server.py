"""
Production-grade Static + Reverse Proxy Server for MindMesh Mobile Web.
Serves dist/ directory and transparently reverse-proxies all /api/* requests to FastAPI backend (127.0.0.1:8002).
"""
import http.server
import socketserver
import urllib.request
import urllib.error
from pathlib import Path
import os
import sys

PORT = 3000
DIST_DIR = Path(__file__).resolve().parent / "dist"
BACKEND_BASE = "http://127.0.0.1:8002"

class MindMeshProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "*")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/") or self.path == "/health":
            self._proxy("GET")
        else:
            # Check if file exists, else fallback to index.html for SPA client-side routes
            requested_file = (DIST_DIR / self.path.lstrip("/")).resolve()
            try:
                is_within_dist = str(requested_file).startswith(str(DIST_DIR))
            except Exception:
                is_within_dist = False

            if not is_within_dist or not requested_file.exists() or requested_file.is_dir():
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/") or self.path == "/health":
            self._proxy("POST")
        else:
            self.send_error(405, "Method Not Allowed")

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy("PUT")
        else:
            self.send_error(405, "Method Not Allowed")

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy("DELETE")
        else:
            self.send_error(405, "Method Not Allowed")

    def do_PATCH(self):
        if self.path.startswith("/api/"):
            self._proxy("PATCH")
        else:
            self.send_error(405, "Method Not Allowed")

    def _proxy(self, method: str):
        target_url = f"{BACKEND_BASE}{self.path}"
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req = urllib.request.Request(target_url, data=body, method=method)
        # Forward request headers except host
        for key, val in self.headers.items():
            if key.lower() not in ("host", "content-length"):
                req.add_header(key, val)

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "content-length"):
                        self.send_header(key, val)
                content = resp.read()
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as err:
            self.send_response(err.code)
            for key, val in err.headers.items():
                if key.lower() not in ("transfer-encoding", "content-length"):
                    self.send_header(key, val)
            content = err.read()
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            self.send_error(502, f"MindMesh Proxy Error: {exc}")

    def log_message(self, format, *args):
        # Concise logging
        sys.stderr.write(f"[WebProxy] {args[0]} - {args[1]}\n")

class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    print(f"Starting MindMesh Threaded Web Proxy on port {PORT} (serving {DIST_DIR} -> proxying to {BACKEND_BASE})...")
    with ReusableTCPServer(("0.0.0.0", PORT), MindMeshProxyHandler) as httpd:
        httpd.serve_forever()
