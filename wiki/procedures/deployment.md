---
type: procedural
zone: procedures
last_updated: 2026-05-07
source_files:
  - README.md
  - docker-compose.prod.yml
  - backend/scripts/register_webhook.py
related:
  - "[[docker]]"
  - "[[api]]"
---

# Deployment & Maintenance

This page documents the steps required to deploy the Matsu Shi stack to a production environment and perform routine maintenance.

## Production Deployment

### 1. Prerequisites
- VPS (e.g., Hetzner CX31) with Docker and Docker Compose installed.
- Domain name with A-record pointing to the VPS.
- Cloudflare R2 bucket and API keys.

### 2. Environment Setup
Copy `.env.example` to `.env` and set `ENVIRONMENT=production`. Ensure all secret keys and API endpoints are populated.

### 3. SSL Configuration
Obtain a certificate via Certbot:
```bash
certbot certonly --standalone -d yourdomain.com
```
Update `docker/nginx/nginx.prod.conf` with the correct domain path for `ssl_certificate` and `ssl_certificate_key`.

> [!CAUTION]
> **Hardcoded Domain**: The production Nginx configuration (`docker/nginx/nginx.prod.conf`) currently has a hardcoded domain `matsushi.xyz`. You **must** replace all occurrences of this domain with your own before launching services.

### 4. Launch Services
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 5. Bot Webhook Registration
The bot defaults to polling in dev, but requires a webhook in production:
```bash
docker compose exec backend python scripts/register_webhook.py
```

### 6. Create Admin User
Initialize the dashboard access:
```bash
docker compose exec backend python scripts/create_admin.py --username admin --password your-secure-password
```
*Note: Password must be at least 8 characters.*

## Routine Maintenance

### Database Migrations
Migrations are applied automatically when the backend container starts. To check status:
```bash
docker compose exec backend alembic current
```

### Monitoring Logs
View real-time logs for the RAG pipeline and bot:
```bash
docker compose logs -f backend
```

### System Health
Check the `/health` endpoint or use the Telegram bot's **`/stats`** command (only available to the user defined in `ADMIN_TELEGRAM_ID`) to verify:
- **User Counts**: Break down of users by status (active, pending, etc.).
- **Query Volume**: Total number of queries processed today.
- **RAG Quality**: Average retrieval score over the last 7 days.

## Troubleshooting

- **502 Bad Gateway**: Usually occurs if the `backend` container is restarted but `nginx` is not. Run `docker compose restart nginx`.
- **Bot not responding**: Verify the webhook URL is correct using `scripts/register_webhook.py --check`. Ensure the VPS firewall allows traffic on port 443.
- **SSE Streaming issues**: Ensure `proxy_buffering off` is set in the Nginx config for the `/api/v1/chat/query` location.

> 💡 Tip: Use `docker compose ps` to verify that the `postgres` healthcheck is passing before investigating backend failures.
