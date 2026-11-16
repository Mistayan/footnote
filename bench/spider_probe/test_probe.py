"""Exercise the independent Spider adapter against a local robots-protected fixture."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import threading

binary = Path(sys.argv[1]).resolve()
visits = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        visits.append(self.path)
        if self.path == "/robots.txt":
            body = b"User-agent: *\nDisallow: /docs/private\n"
            kind = "text/plain"
        elif self.path in ("/docs/", "/docs/a", "/docs/b", "/docs/private", "/outside"):
            body = ("<html><head><title>Documentation</title></head><body><main><h1>Test page</h1>"
                    + "This documentation describes a repeatable local crawler test. " * 8
                    + '<a href="/docs/a">A</a><a href="/docs/b">B</a>'
                    + '<a href="/docs/private">Private</a><a href="/outside">Outside</a>'
                    + "</main></body></html>").encode()
            kind = "text/html"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with tempfile.TemporaryDirectory() as d:
        base = f"http://127.0.0.1:{server.server_port}"
        out = Path(d) / "out"
        run = subprocess.run([str(binary), base + "/docs/", str(out), "2", r"^http://127\.0\.0\.1:\d+/docs(?:/|$)", "-"],
                             capture_output=True, text=True, encoding="utf-8", timeout=40)
        if run.returncode:
            raise RuntimeError(run.stderr)
        report = json.loads(run.stdout)
        pages = json.loads((out / "urls.json").read_text(encoding="utf-8"))
        assert 1 <= report["pages"] <= 2, report
        assert len(pages) == report["pages"]
        assert all(url.startswith(base + "/docs/") for url in pages.values()), pages
        assert "/docs/private" not in visits and "/outside" not in visits, visits
        assert "/robots.txt" in visits, visits
        print(json.dumps({"fixture": "pass", "pages": report["pages"], "visited": visits}))
finally:
    server.shutdown()
    server.server_close()
    thread.join()
