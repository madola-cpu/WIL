"""A small HTTP service so any backend or frontend can call Phase 4 (no dependencies).

    python -m phase4 serve --port 8040

GET  /health                       engine version, catalogs, profiles
GET  /schemas/<name>               input | output | manager-view | phase3-profile
GET  /profiles                     client profile names
POST /phase4/run                   body: Phase 4 input         -> Phase 4 output   (?view=manager for the manager view)
POST /phase4/from-phase3           body: {phase3, profile, mapping}             -> {phase4_input, mapping_report}
POST /phase4/pipeline              body: {phase3, profile, mapping, expected}   -> every Phase 5 output
POST /phase4/report                body: Phase 4 output        -> {report, report_markdown}
POST /phase4/manager-view          body: Phase 4 output        -> manager view

Errors come back as JSON: 400 bad JSON, 404 unknown path, 413 too large,
422 the input cannot be used ({"errors": [...], "mapping_report": {...}}), 500 anything else.
It binds to 127.0.0.1 by default; it is meant for local use and demos, not the open internet.
"""
from __future__ import annotations

import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .catalog import Catalog
from .connectors.frontend import manager_view
from .connectors.phase3 import Phase3MappingError, from_phase3
from .connectors.phase5 import render_markdown, report_blocks
from .contract import Phase4InputError
from .engine import ENGINE_VERSION, run_phase4
from .pipeline import run_pipeline
from .resources import list_profiles, load_schema

MAX_BODY = 5 * 1024 * 1024


class _Handler(BaseHTTPRequestHandler):
    server_version = f"phase4/{ENGINE_VERSION}"
    cors_origin = "*"
    quiet = False

    # ------------------------------------------------------------ plumbing
    def _send(self, status: int, body: Any) -> None:
        data = b"" if status == 204 else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if data:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if self.cors_origin:
            self.send_header("Access-Control-Allow-Origin", self.cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> Tuple[Optional[Any], Optional[Tuple[int, Dict[str, Any]]]]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return None, (413, {"error": f"body larger than {MAX_BODY} bytes"})
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8") or "null"), None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, (400, {"error": f"body is not valid JSON: {exc}"})

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
        if not self.quiet:
            super().log_message(fmt, *args)

    # ------------------------------------------------------------ routes
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        if path in ("/", "/health"):
            catalogs = [v for s in ("A", "B") for v in Catalog.load(s).versions]
            self._send(200, {"ok": True, "engine": f"phase4 {ENGINE_VERSION}", "catalogs": catalogs,
                             "profiles": list_profiles()})
        elif path == "/profiles":
            self._send(200, {"profiles": list_profiles()})
        elif path.startswith("/schemas/"):
            try:
                self._send(200, load_schema(path.split("/", 2)[2]))
            except (KeyError, FileNotFoundError) as exc:
                self._send(404, {"error": str(exc)})
        else:
            self._send(404, {"error": f"unknown path {path}"})

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path = url.path.rstrip("/")
        body, err = self._body()
        if err:
            self._send(*err)
            return
        try:
            if path == "/phase4/run":
                out = run_phase4(body)
                view = parse_qs(url.query).get("view", [""])[0]
                self._send(200, manager_view(out) if view == "manager" else out)
            elif path == "/phase4/from-phase3":
                body = body or {}
                phase4_input, report = from_phase3(body.get("phase3"), body.get("profile"), body.get("mapping"))
                self._send(200, {"phase4_input": phase4_input, "mapping_report": report})
            elif path == "/phase4/pipeline":
                body = body or {}
                self._send(200, run_pipeline(body.get("phase3"), profile=body.get("profile"),
                                             mapping=body.get("mapping"), expected=body.get("expected")))
            elif path == "/phase4/report":
                report = report_blocks(body)
                self._send(200, {"report": report, "report_markdown": render_markdown(report)})
            elif path == "/phase4/manager-view":
                self._send(200, manager_view(body))
            else:
                self._send(404, {"error": f"unknown path {path}"})
        except Phase3MappingError as exc:
            self._send(422, {"errors": exc.errors, "mapping_report": exc.report})
        except Phase4InputError as exc:
            self._send(422, {"errors": exc.errors})
        except FileNotFoundError as exc:
            self._send(422, {"errors": [str(exc)]})
        except (KeyError, TypeError, AttributeError) as exc:
            self._send(422, {"errors": [f"body does not have the expected shape ({type(exc).__name__}: {exc})"]})
        except Exception as exc:  # pragma: no cover - last resort, keep the service up
            self._send(500, {"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc(limit=3)})


def make_server(host: str = "127.0.0.1", port: int = 8040, cors_origin: str = "*", quiet: bool = False) -> ThreadingHTTPServer:
    handler = type("Phase4Handler", (_Handler,), {"cors_origin": cors_origin, "quiet": quiet})
    return ThreadingHTTPServer((host, port), handler)


def serve(host: str = "127.0.0.1", port: int = 8040, cors_origin: str = "*") -> None:
    server = make_server(host, port, cors_origin)
    print(f"Phase 4 service on http://{host}:{server.server_address[1]}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
