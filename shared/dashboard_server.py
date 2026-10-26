"""BuddyCheck's local HTTP endpoint for public UI assets and browser settings."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from mimetypes import guess_type
import os
import socket
from pathlib import Path
from threading import Thread
from urllib.parse import unquote, urlsplit

from shared.mqtt_connection import DEFAULT_HOST, project_id

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def public_browser_config() -> dict:
    websocket = os.environ.get("MQTT_WS_URL", "").strip()
    if not websocket and os.environ.get("MQTT_HOST", DEFAULT_HOST) == DEFAULT_HOST:
        websocket = "wss://broker.hivemq.com:8884/mqtt"
    return {
        "project_id": project_id(), "websocket_url": websocket,
        "room_mode": "multi",
        "automatic_connection": bool(websocket and not os.environ.get("MQTT_USERNAME", "").strip()),
    }


class DashboardServer(ThreadingHTTPServer):
    # Windows otherwise permits a second process to reuse a listening address.
    allow_reuse_address = not hasattr(socket, "SO_EXCLUSIVEADDRUSE")

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class DashboardHTTP(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self._respond(include_body=False)

    def do_GET(self):
        self._respond(include_body=True)

    def _respond(self, include_body: bool):
        requested = unquote(urlsplit(self.path).path)
        if requested == "/config.json":
            body = json.dumps(public_browser_config()).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            relative = requested.lstrip("/") or "index.html"
            resource = (WEB_DIR / relative).resolve()
            if not resource.is_relative_to(WEB_DIR) or not resource.exists():
                self.send_error(404)
                return
            if resource.is_dir():
                self.send_error(403)
                return
            try:
                body = resource.read_bytes()
            except OSError:
                self.send_error(404)
                return
            content_type = guess_type(resource.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_dashboard_server(port: int | None = None):
    address = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
    selected_port = int(os.environ.get("DASHBOARD_PORT", "8000")) if port is None else port
    server = DashboardServer((address, selected_port), DashboardHTTP)
    worker = Thread(name="buddycheck-http", target=server.serve_forever, daemon=True)
    worker.start()
    return server, worker
