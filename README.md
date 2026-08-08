# LAN Portal

A lightweight LAN dashboard that gives local services memorable URLs without requiring custom DNS or per-service reverse-proxy configuration.

Instead of remembering ports such as `:8096` or `:8989`, visit the portal and use shortcuts such as:

```text
http://server:8088/jellyfin
http://server:8088/sonarr
```

LAN Portal redirects each shortcut to the configured host and port. The target service sees a normal direct connection, so it does not need base-path or proxy-specific configuration.

## Features

- Simple responsive dashboard
- Add services from the dashboard
- Human-readable shortcut paths
- Redirects to services on the same host or other LAN devices
- HTTP and HTTPS targets
- No Python packages beyond the standard library
- Docker Compose / Arcane friendly
- Configuration stored in a small JSON file

## Setup

1. Copy the example configuration:

```sh
cp services.example.json services.json
```

2. Start the project:

```sh
docker compose up -d
```

3. Open `http://SERVER-IP:8088/`.

To use another host port, set `PORTAL_PORT`, for example:

```sh
PORTAL_PORT=80 docker compose up -d
```

In Arcane, add `PORTAL_PORT` as a project environment variable if desired.

## Configuration

`services.json` is intentionally ignored by Git so private LAN hostnames, addresses, and service details are not committed.

A same-host service can omit `host`:

```json
{
  "name": "Example Service",
  "path": "example",
  "port": 8080,
  "description": "Example local service",
  "icon": "◈"
}
```

For another LAN device, provide `host`. For HTTPS targets, set `"scheme": "https"`.

## Dashboard management

Use **Add Service** on the dashboard to add entries without manually editing JSON. The included Compose configuration keeps `services.json` writable while mounting application code and static files read-only.

## Security

LAN Portal is intended for trusted local networks. The management API currently has no authentication. Do not expose it directly to the public internet without adding authentication and other appropriate protections.
