import json
import mimetypes
import os
import re
import socket
from html import escape
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/app/services.json"))
TEMPLATE_PATH = Path(os.environ.get("TEMPLATE_PATH", "/app/templates/index.html"))
STATIC_PATH = Path(os.environ.get("STATIC_PATH", "/app/static"))
FAVICON_CACHE_PATH = Path(os.environ.get("FAVICON_CACHE_PATH", "/app/favicons"))
PORT = int(os.environ.get("PORT", "8080"))
PATH_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
FAVICON_MAX_BYTES = 262144
FAVICON_TIMEOUT_SECONDS = 4
FAVICON_CONTENT_TYPES = {
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class IconLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icons = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return

        values = {name.lower(): value for name, value in attrs if value}
        rels = set(values.get("rel", "").lower().split())
        href = values.get("href", "").strip()
        if href and "icon" in rels:
            self.icons.append(href)


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_config(config):
    temp_path = CONFIG_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2, ensure_ascii=False)
        file.write("\n")
    try:
        temp_path.replace(CONFIG_PATH)
    except OSError:
        with CONFIG_PATH.open("w", encoding="utf-8") as file:
            json.dump(config, file, indent=2, ensure_ascii=False)
            file.write("\n")
        try:
            temp_path.unlink()
        except OSError:
            pass


def build_target(service, request_host):
    scheme = service.get("scheme", "http")
    host = service.get("host") or request_host
    port = service.get("port")
    return f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"


def get_request_host(headers):
    return headers.get("Host", "").split(":")[0]


def request_url(url, max_bytes=None):
    request = Request(url, headers={"User-Agent": "LAN Portal favicon fetcher"})
    with urlopen(request, timeout=FAVICON_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        data = response.read((max_bytes or FAVICON_MAX_BYTES) + 1)
    if max_bytes and len(data) > max_bytes:
        raise ValueError("Favicon response is too large.")
    return data, content_type


def discover_favicon_urls(target):
    urls = []
    try:
        body, _ = request_url(target, max_bytes=FAVICON_MAX_BYTES)
    except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError):
        body = b""

    if body:
        parser = IconLinkParser()
        try:
            parser.feed(body.decode("utf-8", errors="ignore"))
            urls.extend(urljoin(target, href) for href in parser.icons)
        except Exception:
            pass

    urls.append(urljoin(target.rstrip("/") + "/", "favicon.ico"))
    return urls


def get_favicon_extension(url, content_type):
    content_type = content_type.split(";", 1)[0].strip().lower()
    if content_type in FAVICON_CONTENT_TYPES:
        return FAVICON_CONTENT_TYPES[content_type]

    extension = Path(urlparse(url).path).suffix.lower()
    if extension in set(FAVICON_CONTENT_TYPES.values()):
        return extension
    return ".ico"


def cache_service_favicon(service, request_host):
    target = build_target(service, request_host)
    try:
        FAVICON_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    for favicon_url in discover_favicon_urls(target):
        try:
            data, content_type = request_url(favicon_url, max_bytes=FAVICON_MAX_BYTES)
        except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError):
            continue

        if not data:
            continue

        extension = get_favicon_extension(favicon_url, content_type)
        cache_name = f"{service['path']}{extension}"
        cache_path = FAVICON_CACHE_PATH / cache_name
        try:
            cache_path.write_bytes(data)
        except OSError:
            return
        service["favicon"] = cache_name
        return


def render_service_cards(services):
    cards = []
    for service in services:
        name = escape(str(service["name"]))
        path = escape(str(service["path"]).strip("/"))
        description = escape(str(service.get("description", "")))
        icon = escape(str(service.get("icon", "\u25c8")))
        favicon = str(service.get("favicon", "")).strip()
        icon_html = icon
        if favicon:
            icon_html = f'<img src="/favicons/{escape(favicon)}" alt="" loading="lazy">'
        service_json = escape(json.dumps(service, ensure_ascii=False), quote=True)
        cards.append(f"""
        <article class="service-card-shell" data-service="{service_json}">
            <a class="service-card" href="/{path}">
                <div class="service-icon">{icon_html}</div>
                <div class="service-content">
                    <div class="service-name">{name}</div>
                    <div class="service-description">{description}</div>
                </div>
                <div class="service-arrow" aria-hidden="true">&rarr;</div>
            </a>
            <button class="service-edit-button" type="button" data-service-path="{path}" aria-label="Edit {name}">Edit</button>
        </article>
        """)
    return "\n".join(cards)


def render_dashboard(config):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    title = escape(str(config.get("title", "Home Server")))
    subtitle = escape(str(config.get("subtitle", "Services and devices on your network")))
    services_html = render_service_cards(config.get("services", []))
    return template.replace("{{TITLE}}", title).replace("{{SUBTITLE}}", subtitle).replace("{{SERVICES}}", services_html)


def validate_service(payload, existing_services, original_path=None):
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
    if path.lower() in {"api", "static", "favicons"}:
        raise ValueError(f'Path "{path}" is reserved.')

    for service in existing_services:
        existing_path = str(service.get("path", "")).strip("/")
        if original_path and existing_path.lower() == original_path.lower():
            continue
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
            return self.serve_file(path, "/static/", STATIC_PATH, "no-cache")
        if path.startswith("/favicons/"):
            return self.serve_file(path, "/favicons/", FAVICON_CACHE_PATH, "public, max-age=86400")
        if path == "/api/services":
            return self.get_services()
        self.redirect_service(path)

    def do_POST(self):
        if urlparse(self.path).path == "/api/services":
            return self.add_service()
        self.send_json(404, {"error": "Endpoint not found."})

    def do_PUT(self):
        path = urlparse(self.path).path
        if path.startswith("/api/services/"):
            return self.update_service(unquote(path.removeprefix("/api/services/")))
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

    def serve_file(self, request_path, url_prefix, root_path, cache_control):
        relative_path = request_path.removeprefix(url_prefix)
        if not relative_path:
            return self.send_error(404)

        root = root_path.resolve()
        requested_file = (root_path / relative_path).resolve()
        try:
            requested_file.relative_to(root)
        except ValueError:
            return self.send_error(403)

        if not requested_file.exists() or not requested_file.is_file():
            return self.send_error(404)

        content_type, _ = mimetypes.guess_type(str(requested_file))
        body = requested_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)

    def get_services(self):
        try:
            self.send_json(200, {"services": load_config().get("services", [])})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("Request body is empty.")
        if content_length > 65536:
            raise ValueError("Request body is too large.")
        return json.loads(self.rfile.read(content_length).decode("utf-8"))

    def add_service(self):
        try:
            payload = self.read_json_body()
            config = load_config()
            services = config.setdefault("services", [])
            service = validate_service(payload, services)
            cache_service_favicon(service, get_request_host(self.headers))
            services.append(service)
            save_config(config)
            self.send_json(201, service)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON."})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": f"Failed to save service: {exc}"})

    def update_service(self, original_path):
        try:
            original_path = original_path.strip("/")
            if not original_path:
                raise ValueError("Service path is required.")

            payload = self.read_json_body()
            config = load_config()
            services = config.setdefault("services", [])
            service_index = next(
                (index for index, service in enumerate(services)
                 if str(service.get("path", "")).strip("/").lower() == original_path.lower()),
                None
            )
            if service_index is None:
                self.send_json(404, {"error": "Service not found."})
                return

            existing_service = services[service_index]
            service = validate_service(payload, services, original_path=original_path)
            same_target = all(
                existing_service.get(key) == service.get(key)
                for key in ("path", "host", "port", "scheme")
            )
            if same_target and existing_service.get("favicon"):
                service["favicon"] = existing_service["favicon"]
            cache_service_favicon(service, get_request_host(self.headers))
            services[service_index] = service
            save_config(config)
            self.send_json(200, service)
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
            target = build_target(service, get_request_host(self.headers))
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
