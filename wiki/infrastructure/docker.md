---
type: architecture
zone: infrastructure
last_updated: 2026-05-07
source_files:
  - docker-compose.yml
  - docker-compose.prod.yml
  - docker/nginx/nginx.prod.conf
  - backend/Dockerfile
  - frontend/Dockerfile
related:
  - "[[overview]]"
  - "[[api]]"
  - "[[database]]"
---

# Infrastructure & Docker

Matsu Shi is a containerized application orchestrated by **Docker Compose**. It follows a microservices-inspired architecture where the backend, frontends, and data stores are isolated in specialized containers.

## Service Stack

| Service | Image / Base | Role |
| :--- | :--- | :--- |
| **Backend** | `python:3.13-slim` | FastAPI server + Telegram Bot |
| **Frontend** | `nginx:alpine` | Telegram Mini App (Static bundle) |
| **Admin** | `nginx:alpine` | Admin Dashboard (Static bundle) |
| **Postgres** | `pgvector:pg16` | Relational + Vector storage |
| **Redis** | `redis:7-alpine` | Rate limiting |
| **Nginx** | `nginx:alpine` | SSL Termination & Gateway |

## Nginx Gateway Configuration

The entry point for all external traffic is the Nginx gateway. It handles SSL termination and routes requests based on the URL path.

### Key Production Rules:
- **SSL**: Certificates are managed by Let's Encrypt and mounted into the container at `/etc/letsencrypt`.
- **SSE Support**: The diagnostic endpoint (`/api/v1/chat/query`) has buffering disabled to allow real-time streaming:
  ```nginx
  proxy_buffering off;
  add_header X-Accel-Buffering no;
  ```
- **Dynamic Resolution**: Uses Docker's internal DNS (`127.0.0.11`) to re-resolve service IPs, preventing downtime during container restarts.
- **Routing**:
  - `/api/` → Backend
  - `/admin/` → Admin Dashboard (rewrites `/admin/` prefix to `/`)
  - `/` → Telegram Mini App

## Deployment Environments

### Development (`docker-compose.yml`)
- **Hot Reload**: Backend and Frontends mount local directories as volumes.
- **Bot Mode**: Long polling is used for instant response to code changes.
- **Exposed Ports**: Services are directly accessible on `localhost` (8000, 5173, 5174).

### Production (`docker-compose.prod.yml`)
- **Optimization**: Frontends are served as minified static assets via Nginx.
- **Security**: The database port is bound to `127.0.0.1`, allowing access only via SSH tunnel.
- **Bot Mode**: Webhooks are configured via the `webhook/telegram` endpoint.
- **Stability**: Containers use `restart: unless-stopped`.

## Build Pipeline

The **Backend Dockerfile** uses `uv` for extremely fast dependency installation. It leverages multi-stage builds to provide a lean production image while maintaining a feature-rich `dev` target for testing.

```dockerfile
# UV-based dependency install
RUN pip install uv
ENV UV_SYSTEM_PYTHON=1
RUN uv pip install -r pyproject.toml

# System dependencies (OCR & Image processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 libx11-6 libxext6 libxrender1 libgomp1 \
    libgl1 libglib2.0-0 tesseract-ocr tesseract-ocr-rus

# Automatic migrations on startup
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app ..."]
```

> [!CAUTION]
> **Hardcoded Domain**: The production Nginx configuration (`docker/nginx/nginx.prod.conf`) currently has a hardcoded domain `matsushi.xyz` in the SSL certificate paths. This file **must** be updated manually before deploying to a new domain.
