import json
import mimetypes
import os
import re
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/app/services.json"))
TEMPLATE_PATH = Path(os.environ.get("TEMPLATE_PATH", "/app/templates/index.html"))
STATIC_PATH = Path(os.environ.get("STATIC_PATH", "/app/static"))
PORT = int(os.environ.get("PORT", "8080"))
PATH_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_config(config):
    temp_path = CONFIG_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2, ensure_ascii=False)
        file.write("\n")
    temp_path.replace(CONFIG_PATH)


def build_target(service, request_host):
    scheme = service.get("scheme", "http")
    host = service.get("host") or request_host
    port = service.get("port")
    return f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"


def render_service_cards(services):
    cards = []
    for service in services:
        name = escape(str(service["name"]))
        path = escape(str(service["path"]).strip("/"))
        description = escape(str(service.get("description", "")))
        icon = escape(str(service.get("icon", "◈")))
        cards.append(f"""
        <a class="service-card" href="/{path}">
            <div class="service-icon">{icon}</div>
            <div class="service-content">
                <div class="service-name">{name}</div>
                <div class="service-description">{description}</div>
            </div>
            <div class="service-arrow" aria-hidden="true">→</div>
        </a>
        """)
    return "\n".join(cards)


def render_dashboard(config):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    title = escape(str(config.get("title", "Home Server")))
    subtitle = escape(str(config.get("subtitle", "Services and devices on your network")))
    services_html = render_service_cards(config.get("services", []))
    return template.replace("{{TITLE}}", title).replace("{{SUBTITLE}}", subtitle).replace("{{SERVICES}}", services_html)


def validate_service(payload, existing_services):
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object.")

    name = str(payload.get("name", "")).strip()
    path = str(payload.get("path", "")).strip().strip("/")
    description = str(payload.get("description", "")).strip()
    icon = str(payload.get("icon", "")).strip()
    host = str(payload.get("host", "")).strip()
    scheme = str(payload.get("scheme", "http")).strip().lower()

    if not name:
        raise ValueError("Name is required.")
    if not path:
        raise ValueError("Path is required.")
    if not PATH_PATTERN.fullmatch(path):
        raise ValueError("Path may only contain letters, numbers, and hyphens.")
    if path.lower() in {"api", "static"}:
        raise ValueError(f'Path "{path}" is reserved.')

    for service in existing_services:
        existing_path = str(service.get("path", "")).strip("/")
        if existing_path.lower() == path.lower():
            raise ValueError(f'A service using "/{path}" already exists.')

    try:
        port = int(payload.get("port"))
    except (TypeError, ValueError):
        raise ValueError("Port must be a number.")

    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    if scheme not in {"http", "https"}:
        raise ValueError("Protocol must be http or https.")

    service = {"name": name, "path": path, "port": port}
    if description:
        service["description"] = description
    if icon:
        service["icon"] = icon
    if host:
        service["host"] = host
    if scheme != "http":
        service["scheme"] = scheme
    return service


class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.serve_dashboard()
        if path.startswith("/static/"):
            return self.serve_static(path)
        if path == "/api/services":
            return self.get_services()
        self.redirect_service(path)

    def do_POST(self):
        if urlparse(self.path).path == "/api/services":
            return self.add_service()
        self.send_json(404, {"error": "Endpoint not found."})

    def serve_dashboard(self):
        try:
            body = render_dashboard(load_config()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            self.send_error(500, f"Failed to render dashboard: {exc}")

    def serve_static(self, request_path):
        relative_path = request_path.removeprefix("/static/")
        if not relative_path:
            return self.send_error(404)

        static_root = STATIC_PATH.resolve()
        requested_file = (STATIC_PATH / relative_path).resolve()
        try:
            requested_file.relative_to(static_root)
        except ValueError:
            return self.send_error(403)

        if not requested_file.exists() or not requested_file.is_file():
            return self.send_error(404)

        content_type, _ = mimetypes.guess_type(str(requested_file))
        body = requested_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def get_services(self):
        try:
            self.send_json(200, {"services": load_config().get("services", [])})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def add_service(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                raise ValueError("Request body is empty.")
            if content_length > 65536:
                raise ValueError("Request body is too large.")

            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            config = load_config()
            services = config.setdefault("services", [])
            service = validate_service(payload, services)
            services.append(service)
            save_config(config)
            self.send_json(201, service)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON."})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": f"Failed to save service: {exc}"})

    def redirect_service(self, request_path):
        try:
            config = load_config()
        except Exception as exc:
            return self.send_error(500, f"Failed to load services: {exc}")

        requested_path = request_path.strip("/")
        for service in config.get("services", []):
            if requested_path != str(service["path"]).strip("/"):
                continue
            request_host = self.headers.get("Host", "").split(":")[0]
            target = build_target(service, request_host)
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.send_error(404, "Service not found")

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), PortalHandler)
    print(f"LAN Portal listening on port {PORT}")
    server.serve_forever()
