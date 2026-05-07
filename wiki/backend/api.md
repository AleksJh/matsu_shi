---
type: component
zone: backend
last_updated: 2026-05-07
source_files:
  - backend/app/main.py
  - backend/app/api/auth.py
  - backend/app/api/chat.py
  - backend/app/api/admin.py
  - backend/app/api/feedback.py
  - backend/app/core/security.py
related:
  - "[[overview]]"
  - "[[agents]]"
  - "[[bot]]"
---

# API Layer

The Matsu Shi API is built with **FastAPI** and serves as the central orchestration point for the Telegram Mini App and Admin Dashboard. All endpoints are versioned under `/api/v1`.

## Authentication Flow

### Mechanic Auth (Telegram Mini App)
1.  **Handshake**: The Mini App sends Telegram `initData` to `POST /auth/telegram`.
2.  **Validation**: The backend verifies the HMAC signature using the `BOT_TOKEN` (via `aiogram.utils.web_app.safe_parse_webapp_init_data`).
3.  **Status Check**: The user must be registered via the [[bot]] and have a status of `active`.
4.  **JWT Issue**: A token is issued with `role=mechanic` and `sub=telegram_user_id`.

### Admin Auth (Dashboard)
1.  **Login**: `POST /auth/admin/login` accepts username and password.
2.  **Validation**: Password verified via `bcrypt`.
3.  **JWT Issue**: A token is issued with `role=admin`.

## Key Endpoints

### Chat & Diagnostics (`/chat/`)
- **`POST /chat/query` (SSE Stream)**: The primary diagnostic endpoint.
  - Takes `session_id` and `query_text`.
  - Runs the complete [[agents]] and [[rag-pipeline]].
  - Returns a `text/event-stream` with a single `QueryResponse` event.
  - **Side Effects**: Persists the query to the [[database]] and triggers an auto-title generation background task for new sessions.
- **`GET /chat/sessions/{id}/history`**: Returns the full message history for a specific session.
- **`GET /chat/models`**: Lists available machine models (e.g., "PC300-8") derived from indexed documents.

### Feedback (`/feedback/`)
- **`POST /feedback/{query_id}`**: Submit thumbs up (`1`) or thumbs down (`-1`) for a specific query response.
  - Requires `mechanic` role.
  - Enforces a unique constraint: only one feedback entry per query.

### Admin Operations (`/admin/`)
- **User Management**: `GET /users`, `PUT /users/{id}/status` (approve/deny/ban), `DELETE /users/{id}`.
- **Monitoring**: `GET /stats` provides aggregated system metrics, model usage breakdown, and feedback counts.
- **Broadcast**: `POST /broadcast` allows sending a Telegram message to all active mechanics simultaneously.

## Security & Rate Limiting

- **JWT**: Enforced via `get_current_user` and `get_current_admin` dependencies.
- **Rate Limiting**: Redis-based limit of **15 requests per minute** per user. Exceeding this returns a `429 Too Many Requests`.
- **Webhook Security**: `POST /webhook/telegram` is protected by a `X-Telegram-Bot-Api-Secret-Token` header check.

## SSE Implementation Details
The `query_endpoint` in `app/api/chat.py` uses a custom `event_generator` to ensure that data is delivered before the background persistence task begins.
```python
async def event_generator():
    yield f"data: {response.model_dump_json()}\n\n"
    await svc.persist_query(...) # Non-blocking persistence
```

> ⚠️ Known issue: `X-Accel-Buffering: no` header is required for Nginx to ensure SSE events are not buffered in production.
