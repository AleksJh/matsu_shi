# Matsu Shi — Developer Roadmap
> Target: Claude Code AI agent under human supervision
> Language: All UI, prompts, and user-facing strings → Russian. Code, comments, docs → English
> Architecture reference: PRD.md (always consult for specs, schemas, thresholds, and naming)

---

## GROUND RULES FOR THE AGENT

- Always re-read the relevant PRD section before starting any phase.
- Never invent API contracts, schema fields, or model names — derive everything from PRD.md.
- Each phase must be fully functional and manually verifiable before moving to the next.
- Commit after each completed phase with a descriptive message.
- Never store secrets in code. All secrets go into `.env` (never committed).
- All new text shown to users must be in Russian.

---

## ✅ PHASE 0 — Repository & Project Scaffold

**Goal:** Empty repo becomes a working monorepo skeleton with Docker Compose running locally.

### ✅ 0.1 Monorepo Structure
- Create the full directory tree as defined in PRD §9.1 (all folders, empty `__init__.py` where needed, placeholder `README.md` files per package).
- Do not create files for code that will be written in later phases — only scaffold directories and package entry points.

### ✅ 0.2 Backend Python Project
- Initialize `backend/pyproject.toml` managed by `uv`.
- Add all production dependencies listed across the PRD (FastAPI, aiogram, pydantic-ai, sqlalchemy, asyncpg, alembic, langfuse, loguru, llama-index, boto3, pillow, python-jose, passlib, redis, etc.).
- Add dev/test dependencies (pytest, pytest-asyncio, httpx, ruff, mypy).
- Create `backend/app/core/config.py` using `pydantic-settings`: define all env vars from PRD §10 with correct types and defaults.
- Create `backend/app/core/logging.py`: configure Loguru for structured stdout output.

### ✅ 0.3 Frontend Projects
- Initialize `frontend/` as a Vite + React 18 + TypeScript + Tailwind CSS project (Telegram Mini App).
- Initialize `admin-frontend/` as a separate Vite + React 18 + TypeScript + Tailwind CSS project (Admin Dashboard).
- Configure both projects' `vite.config.ts` to proxy API requests to `http://localhost:8000` in development.

### ✅ 0.4 Docker Compose (Development)
- Write `docker-compose.yml` defining all six services from PRD §9.2: `backend`, `frontend`, `admin`, `postgres` (with pgvector extension), `redis`, `nginx`.
- Postgres service must run the pgvector extension init SQL on first start.
- Mount local source directories as volumes for hot-reload in development.
- Expose ports: backend 8000, frontend 5173, admin 5174, postgres 5432, redis 6379.

### ✅ 0.5 Environment & Git Setup
- Create `.env.example` with all variables from PRD §10, values left blank, with inline comments explaining each.
- Create `.gitignore` covering Python, Node, Docker, and `.env` files.
- Write a minimal `README.md` explaining how to clone, copy `.env.example` to `.env`, and run `docker compose up`.

### ✅ 0.6 Database Migrations (Alembic)
- Initialize Alembic in `backend/alembic/`.
- Write the initial migration creating all six tables from PRD §9.3 in correct dependency order: `users`, `admin_users`, `documents`, `chunks` (with HNSW index and machine_model index), `diagnostic_sessions`, `queries`, `feedback`.
- The `embedding` column dimension must be read from an env var `EMBED_DIM` (to be filled once confirmed from OpenRouter).
- Verify migration applies cleanly against the Dockerized Postgres with `alembic upgrade head`.

**Phase 0 Done When:** `docker compose up` starts all services without errors; Alembic migration applies; frontend dev servers load blank pages at their respective ports.

---

## ✅ PHASE 1 — Telegram Bot & Auth State Machine

**Goal:** The Telegram bot handles the full mechanic registration flow and all admin commands.

### ✅ 1.1 Bot Initialization
- Set up aiogram 3.x `Dispatcher` and `Bot` in `backend/app/bot/`.
- Configure webhook mode (for production) and polling mode (for local development) switchable via `ENVIRONMENT` env var.
- Register the bot router in the FastAPI app at `POST /webhook/telegram`.

### ✅ 1.2 Mechanic `/start` Handler
- On `/start` from an unknown user: create a `users` record with `status = pending`, capturing `telegram_user_id`, `username`, `first_name`.
- Send the admin (identified by `ADMIN_TELEGRAM_ID`) a Telegram notification listing the new user's name and username, with two inline keyboard buttons: `✅ Approve` and `❌ Deny`.
- Reply to the mechanic in Russian that their request is under review.
- On `/start` from a `pending` user: remind them their request is still being reviewed.
- On `/start` from an `active` user: send the Mini App launch button (`WebAppButton`) pointing to `APP_BASE_URL/frontend`.
- On `/start` from `denied` or `banned` users: send a Russian rejection message, no further action.

### ✅ 1.3 Admin Inline Button Callbacks
- `✅ Approve` callback: set `status = active`, set `approved_at` and `approved_by`, notify the mechanic in Russian that access is granted.
- `❌ Deny` callback: set `status = denied`, notify the mechanic in Russian that access is denied.
- `🚫 Ban` callback (triggered from `/users` command, not from approval flow): set `status = banned`, notify the mechanic in Russian.

### ✅ 1.4 Admin Bot Commands
- `/users` — send a paginated inline list of all users grouped by status; each user row has `Approve`/`Deny`/`Ban` action buttons as appropriate.
- `/stats` — query the database: total queries today, count of active users, average retrieval score over the last 7 days; format as a Russian-language summary message.
- `/notify <text>` — broadcast the provided text to all `active` users via individual Telegram messages. Confirm count sent to admin.

### ✅ 1.5 User Service
- Create `backend/app/services/user_service.py` with async methods: `create_pending`, `get_by_telegram_id`, `update_status`, `list_by_status`, `get_stats`.
- All DB operations via SQLAlchemy async session.

**Phase 1 Done When:** New user triggers admin notification with working approve/deny buttons; approved user receives Mini App button; `/users`, `/stats`, `/notify` all return correct data.

---

## ✅ PHASE 2 — PDF Ingestion Pipeline (Local CLI)

**Goal:** `ingest.py` processes a local PDF end-to-end and writes vectors + metadata to the remote database and images to Cloudflare R2.

### ✅ 2.1 CLI Entry Point
- Create `backend/scripts/ingest.py` as a standalone CLI using `argparse`.
- Support flags: `--path <file>`, `--dir <directory>`, `--machine-model <string>`, `--category <string>`, `--rebuild-index`, `--dry-run`.
- Load environment variables from `.env` at project root using `python-dotenv`.
- Initialize Loguru for structured CLI output (progress per step, final summary: N chunks indexed, M images uploaded).

### ✅ 2.2 Step 1 — Docling Parse
- For each PDF file: run Docling parser to extract Markdown output with heading hierarchy preserved (H1–H4).
- Capture figure/image position metadata per page: `page_number` and bounding box where available.
- Compute SHA-256 checksum of the PDF file.
- If `--rebuild-index` is not set and checksum already exists in `documents` table: skip and log.

### ✅ 2.3 Step 2 — Visual Ingestion (parallel with Step 3)
- For each page that Docling identifies as containing a diagram, schematic, or drawing:
  - Render the page as a WebP image at 150 DPI.
  - Upload to Cloudflare R2 at path `{machine_model}/{doc_name}/page_{n}.webp` using boto3 S3-compatible client.
  - Send the WebP to Gemini vision model (use `LLM_ADVANCED_MODEL`) with the Russian prompt from PRD §4.1.
  - Store result as a `visual_tag`: `{ page_number, r2_url, description }` in memory for use in Step 3.
- Run this step concurrently with Step 3 using asyncio task groups.

### ✅ 2.4 Step 3 — Chunking (4 Rules from PRD §4.2)
- Parse the Docling Markdown output into logical sections using H1–H4 headings as primary chunk boundaries.
- Rule 1: Never split a heading's content across chunks; keep sequential procedural steps together.
- Rule 2: Detect Markdown tables; isolate each table as a single `table`-type chunk. Do not split tables.
- Rule 3: For any text chunk that references "Figure N", "Рис. N", or "Схема N", attach the matching R2 URL(s) from `visual_tags` as `visual_refs`. Create a separate `visual_caption` chunk for each figure page using its Gemini description.
- Rule 4: Apply 10% token overlap between adjacent `text`-type chunks. Do not apply overlap to `table` or `visual_caption` chunks.
- Assign all metadata fields per chunk as defined in PRD §4.3.

### ✅ 2.5 Step 4 — Contextual Enrichment
- For each `text` chunk and `visual_caption` chunk: call Gemini (`LLM_ADVANCED_MODEL`) with the Russian enrichment prompt from PRD §4.1.
- Prepend `"[Контекст: {summary}]\n\n"` to the chunk content before embedding.
- For `table` chunks: prepend the Gemini-generated context header (Rule 2) instead; skip the enrichment API call.

### ✅ 2.6 Step 5 — Embedding
- For each enriched chunk: call the OpenRouter API with model `EMBED_MODEL` (qwen3-embedding-4b) to generate a float vector.
- Confirm embedding dimension from the first API response and validate it matches `EMBED_DIM` env var (error out if mismatch).

### ✅ 2.7 Step 6 — Remote Write
- Insert or update the `documents` record (upsert by checksum).
- Batch-insert all chunk rows with their embedding vectors into `chunks` using asyncpg for performance.
- If `--rebuild-index`: delete existing chunks for this document's `doc_id` before inserting.
- If `--dry-run`: skip all writes; log what would be written.
- Log final summary: document name, chunk count, image count, elapsed time.

**Phase 2 Done When:** Running `ingest.py --path ./test.pdf --machine-model "PC300-8"` on a real PDF produces rows in `documents` and `chunks`, WebP files in R2, and no errors.

---

## ✅ PHASE 3 — Hybrid Retrieval Pipeline

**Goal:** Given a query text and machine_model, return the top-5 most relevant chunks.

### ✅ 3.1 Query Embedding
- Create `backend/app/rag/embedder.py`: async function that calls OpenRouter with `EMBED_MODEL` and returns a float vector.
- Reuse this same embedder in `ingest.py` (import from `app.rag.embedder`).

### ✅ 3.2 Dense Retrieval (pgvector)
- Create `backend/app/rag/dense_retriever.py`: async function that accepts a query vector and `machine_model`.
- Execute pgvector cosine similarity search with `WHERE machine_model = ?` pre-filter, returning top-20 chunks with their cosine scores.

### ✅ 3.3 Sparse Retrieval (BM25)
- Create `backend/app/rag/sparse_retriever.py`: implement BM25 retrieval over the `content` column, pre-filtered by `machine_model`, returning top-20 chunks.
- Use an in-memory BM25 index built at service startup from all chunks for the relevant machine model, or implement via PostgreSQL full-text search (choose the simpler option that fits the MVP scale of 1–20 users).

### ✅ 3.4 Merge, Dedup, Rerank
- Create `backend/app/rag/retriever.py`: orchestrate the full pipeline from PRD §5.2.
- Merge dense top-20 and sparse top-20, deduplicate by `chunk_id`, producing top-40 candidates.
- Send top-40 to Jina AI reranker (`RERANKER_MODEL = jina-reranker-v3`) via Jina API.
- Return top-5 final chunks with full metadata.
- Compute `max_retrieval_score` = maximum cosine similarity score among the top-5.

### ✅ 3.5 Score Threshold Logic
- Implement the three-branch logic from PRD §5.3:
  - Score ≥ 0.65 → flag as `simple` candidate.
  - Score < 0.65 → flag as `complex` candidate (will force advanced model).
  - Score < 0.30 → set `no_answer = True`, skip all downstream LLM calls.

**Phase 3 Done When:** A test Python script calling the retriever with a real query returns 5 ranked chunks with correct metadata and a numeric retrieval score.

---

## ✅ PHASE 4 — LLM Control Plane (Pydantic AI)

**Goal:** ClassifierAgent and ResponderAgent work together to produce structured, grounded responses.

### ✅ 4.1 Pydantic Output Schemas
- Define `Citation` and `QueryResponse` Pydantic models exactly as specified in PRD §6.4.
- Place these in `backend/app/schemas/query.py`.

### ✅ 4.2 ClassifierAgent
- Create `backend/app/agent/classifier.py` using Pydantic AI.
- Model: `LLM_LITE_MODEL` (gemini-2.5-flash-lite).
- Input: query text.
- Output: `query_class` = `"simple"` or `"complex"`.
- Use the classification criteria from PRD §6.2 in the system prompt.

### ✅ 4.3 Model Router
- Create `backend/app/agent/router.py`: implement the routing logic from PRD §6.2.
- Inputs: `max_retrieval_score`, `query_class`.
- Output: model identifier string (`LLM_LITE_MODEL` or `LLM_ADVANCED_MODEL`).

### ✅ 4.4 ResponderAgent
- Create `backend/app/agent/responder.py` using Pydantic AI.
- System prompt: exact Russian-language text from PRD §6.3 — do not modify wording.
- Context injection: format the top-5 chunks (content + section_title + page_number + visual_refs) into the user message as structured context.
- Output: structured `QueryResponse` Pydantic model.
- Enforce that `no_answer = True` responses bypass this agent entirely (return the fixed Russian "not found" string directly).

### ✅ 4.5 Step-by-Step Session Mode (Complex Queries)
- When `query_class == "complex"`: persist reasoning as iterative steps linked to the `diagnostic_sessions` record.
- Each reasoning step is stored as a `queries` row with the same `session_id`.
- Session `status` transitions: `active` → `paused` (on app close) → `active` (on resume) → `completed` (on explicit close).
- The ResponderAgent receives full prior step context when resuming a session.

### ✅ 4.6 Langfuse Tracing
- Instrument the full `process()` call with Langfuse: trace `retrieval_score`, `model_used`, `query_class`, `latency_ms`, `no_answer`.
- Use `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` from config.
- Wrap only the AI calls and retrieval steps; do not trace DB writes.

**Phase 4 Done When:** A test Python script sends a query through the full agent pipeline and returns a populated `QueryResponse` object with citations and correct `model_used`.

---

## ✅ PHASE 5 — FastAPI Backend

**Goal:** All API endpoints from PRD §9.4 are implemented, secured, and working.

### ✅ 5.1 Application Setup
- Create `backend/app/main.py`: instantiate FastAPI app, register all routers, configure CORS for frontend origins.
- Create lifespan handler: initialize DB connection pool, Redis client, bot startup (polling or webhook registration).
- Mount Loguru as the request logger.

### ✅ 5.2 Security Middleware
- Create `backend/app/core/security.py`:
  - Telegram initData HMAC validation (for Mini App auth).
  - JWT creation and verification (for both mechanic and admin tokens).
  - Bcrypt password verification (for admin login).
- Create a reusable FastAPI dependency `get_current_user` that extracts and validates the JWT from `Authorization: Bearer`.
- Create a separate dependency `get_current_admin` for admin-only routes.

### ✅ 5.3 Auth Endpoints
- `POST /api/v1/auth/telegram`: validate Telegram `initData` via HMAC; look up user by `telegram_user_id`; reject if not `active`; return signed JWT.
- `POST /api/v1/auth/admin/login`: validate username + bcrypt password against `admin_users` table; return signed JWT.

### ✅ 5.4 Chat Endpoints
- `POST /api/v1/chat/sessions`: create a new `diagnostic_sessions` record for the authenticated user; require `machine_model` in body.
- `GET /api/v1/chat/sessions`: return all sessions for the authenticated user, ordered by `updated_at` desc.
- `PUT /api/v1/chat/sessions/{id}/status`: update session status to `paused` or `completed`.
- `GET /api/v1/chat/sessions/{id}/history`: return all queries for the session, ordered by `created_at` asc, with response text and citations.
- `POST /api/v1/chat/query`: the core endpoint.
  - Validate JWT → check user `active` status → check Redis rate limit (15 req/min per `user_id`, return HTTP 429 if exceeded).
  - Load session → extract `machine_model`.
  - Call `QueryService.process()` (phases 3 + 4 orchestrated here).
  - Stream the response via SSE (`text/event-stream`).
  - After stream completes: persist the `queries` record asynchronously.

### ✅ 5.5 Feedback Endpoint
- `POST /api/v1/feedback/{query_id}`: insert a `feedback` row with `rating` (1 or -1); enforce the UNIQUE constraint (one vote per query).

### ✅ 5.6 Admin Endpoints
- `GET /api/v1/admin/users`: return paginated user list; support filter by `status`.
- `PUT /api/v1/admin/users/{id}/status`: update user status to `active`, `denied`, or `banned`. If banning an active user, also send a Telegram notification to that user.
- `GET /api/v1/admin/documents`: return all `documents` records with metadata.
- `GET /api/v1/admin/queries`: paginated query log; support filter by `user_id`, date range, `model_used`; truncate `query_text` to 100 chars in list view.
- `GET /api/v1/admin/queries/{id}`: full query detail including full response text and retrieved chunk IDs.
- `GET /api/v1/admin/stats`: aggregate metrics — daily query count (last 30 days), model usage breakdown, average retrieval score trend (weekly), feedback ratio (up vs down).
- `POST /api/v1/admin/broadcast`: accept `{ "message": "..." }`, call bot to send to all `active` users, return count.

### ✅ 5.7 Telegram Webhook Endpoint
- `POST /webhook/telegram`: receive and dispatch aiogram updates. Validate request is from Telegram (secret token header).

### ✅ 5.8 Services
- `QueryService`: orchestrates retrieval (Phase 3) → agent (Phase 4) → DB write → SSE emit.
- `SessionService`: session CRUD and status transitions.
- `FeedbackService`: feedback write with duplicate guard.

**Phase 5 Done When:** All endpoints return correct responses when tested with a REST client (curl or Postman); rate limiting returns 429 on the 16th request; JWT auth rejects tampered tokens.

---

## ✅ PHASE 6 — Telegram Mini App (Frontend)

**Goal:** Mechanics can use the full chat interface inside Telegram.

### ✅ 6.1 Telegram SDK Integration
- Install `@twa-dev/sdk` (Telegram WebApp JS SDK).
- On app load: extract `initData` from `window.Telegram.WebApp.initData`.
- Call `POST /api/v1/auth/telegram` with `initData`; store returned JWT in memory (not localStorage).
- Apply Telegram theme tokens (`colorScheme`, `themeParams`) to Tailwind CSS variables.

### ✅ 6.2 State Management (Zustand)
- Create stores: `authStore` (JWT, user info), `sessionStore` (active session, session list), `messageStore` (messages for active session).
- All API calls go through a typed Axios client in `src/api/` that automatically attaches the JWT header.

### ✅ 6.3 Layout — Two-Panel Structure
- Implement a responsive two-panel layout:
  - Left sidebar (fixed width): machine model selector at top, session list below.
  - Main panel: active chat area.
- On mobile (Telegram WebView narrow mode): sidebar collapses to a toggle drawer.

### ✅ 6.4 Machine Model Selector
- On creating a new session: display available machine models as a chip/button list (fetched from `GET /api/v1/chat/sessions` or a dedicated endpoint that lists indexed models from `documents`).
- Once a model is selected, call `POST /api/v1/chat/sessions` to create the session; lock the model selection for this session; display it in the chat header.

### ✅ 6.5 Session List (Sidebar)
- Fetch and display all user sessions from `GET /api/v1/chat/sessions`.
- Each item: session title (first query text, max 100 chars), status badge (`active` / `paused` / `completed`), relative timestamp.
- Tap a session: load its history from `GET /api/v1/chat/sessions/{id}/history` and display in main panel.
- "New session" button at top of sidebar.

### ✅ 6.6 Chat Message Components
- User message bubble: right-aligned, plain text.
- Assistant message bubble: left-aligned, containing:
  - Markdown-rendered response text (use a lightweight Markdown renderer).
  - Citation block: formatted as `[{doc_name} | {section} | Стр. {page}]`.
  - Inline image viewer: if `visual_url` is present, show a thumbnail that expands on tap.
  - Feedback row: 👍 and 👎 buttons; on click, call `POST /api/v1/feedback/{query_id}`; disable both buttons after one vote.
  - "Расширенный анализ" badge: display only when `model_used == "advanced"`.
- Loading state: animated typing indicator while SSE stream is in progress.

### ✅ 6.7 SSE Streaming
- Implement `useSSE` hook that opens an SSE connection to `POST /api/v1/chat/query`.
- Append streamed tokens to the active message bubble in real time.
- On stream end: parse the final structured `QueryResponse` and attach citations, visual_url, model_used to the message.

### ✅ 6.8 Input Area
- Text input at bottom of chat panel; submit on Enter or button click.
- Disable input while SSE stream is active.
- Show Russian placeholder text.

**Phase 6 Done When:** A mechanic can open the Mini App in Telegram, select a machine model, send a query, see a streamed response with citations, view an image if returned, and submit feedback.

---

## ✅ PHASE 7 — Admin Web Dashboard

**Goal:** Admin can log in and manage the system through a standalone web UI.

### ✅ 7.1 Admin Auth
- Login page: username + password form.
- On submit: call `POST /api/v1/auth/admin/login`; store JWT in `localStorage` with expiry check.
- Route guard: redirect to login if JWT is absent or expired.
- Logout: clear JWT, redirect to login.

### ✅ 7.2 Users Page
- Paginated table: columns — Telegram username, first name, status badge, registered_at, query count.
- Filter bar: filter by status (`pending`, `active`, `denied`, `banned`).
- Actions per row: `Approve`, `Deny`, `Ban` buttons (show only actions relevant to current status).
- Action calls `PUT /api/v1/admin/users/{id}/status`; refresh table on success.

### ✅ 7.3 Documents Page
- Table: document display name, machine_model, category, page_count, chunk_count, indexed_at, status badge.
- No upload UI (ingestion is CLI-only per PRD §11). Read-only view.

### ✅ 7.4 Queries Page
- Paginated log table: user, query text (truncated, 100 chars), model_used badge, retrieval_score, feedback icon (👍/👎/none), timestamp.
- Filters: by user, date range, model_used.
- Row click → open modal with full query text, full response, list of retrieved chunk IDs, latency_ms, all metadata.

### ✅ 7.5 System Page
- Daily query count bar chart (last 30 days).
- Model usage pie chart: lite vs advanced call ratio.
- Average retrieval score line chart (weekly average, last 12 weeks).
- Feedback ratio: percentage thumbs up vs thumbs down.
- All data from `GET /api/v1/admin/stats`.
- Auto-refresh every 60 seconds.

**Phase 7 Done When:** Admin can log in, approve a pending mechanic, see their queries appear in the log, view system metrics.

---

## ✅ PHASE 8 — Infrastructure & Production Deploy

**Goal:** The full system runs on Hetzner VPS with SSL, persisted data, and a registered Telegram webhook.

### ✅ 8.1 Docker Compose (Production)
- Write `docker-compose.prod.yml` extending or overriding dev compose:
  - Remove source volume mounts; use built images only.
  - Add `restart: unless-stopped` to all services.
  - Add named Docker volumes for Postgres data and Redis data.
  - Pass all env vars from the VPS `.env` file.

### ✅ 8.2 Nginx Configuration
- Write `docker/nginx/nginx.conf`:
  - HTTP → HTTPS redirect for all traffic.
  - HTTPS virtual host: proxy `/api/` and `/webhook/` to `backend:8000`; serve `frontend/` static files; serve `admin/` static files at `/admin/`.
  - Enable SSE-compatible proxy settings (`proxy_buffering off`, `X-Accel-Buffering: no`).
  - Set appropriate `client_max_body_size` for any future file uploads.

### ✅ 8.3 VPS Provisioning Steps (document in README, execute manually)
- Document the required steps: install Docker + Compose on Hetzner CX31 Ubuntu, copy repo, copy `.env`, run certbot for Let's Encrypt SSL, start `docker-compose.prod.yml`.
- Do not automate VPS provisioning (out of scope for MVP).

### ✅ 8.4 Telegram Webhook Registration
- Write a one-time script `backend/scripts/register_webhook.py` that calls the Telegram Bot API to set the webhook URL to `https://{APP_BASE_URL}/webhook/telegram` with a secret token.
- The script reads `BOT_TOKEN` and `APP_BASE_URL` from `.env`.

### ✅ 8.5 GitHub Actions CI
- Create `.github/workflows/ci.yml`:
  - Trigger: push to `main` and all pull requests.
  - Jobs: `lint` (ruff + mypy for backend; ESLint for frontends), `test` (pytest for backend unit and integration tests).
  - Do not include auto-deploy in CI for MVP.

### ✅ 8.6 Initial Admin User
- Write a one-time script `backend/scripts/create_admin.py` that accepts `--username` and `--password` CLI args, bcrypt-hashes the password, and inserts a row into `admin_users`.

**Phase 8 Done When:** `docker-compose.prod.yml` starts cleanly on the VPS; HTTPS works; Telegram webhook is registered and receives updates; CI passes on GitHub.

### ✅ 8.7 Ingest Pipeline Checkpointing
- Add `_compute_checksum()`, `_save_artifact()`, `_load_artifact()` to `backend/scripts/ingest.py`.
- Add checkpoint CLI flags: `--stop-after`, `--start-from`, `--save-artifacts`, `--artifact-dir`.
- Artifacts stored as JSON in `cache/{sha256_checksum}/{parse,visual,chunks,enriched,embedded}.json`.
- Enables resuming pipeline from any stage — avoids re-running expensive Docling/Gemini/embedding steps when iterating on chunking or enrichment logic.
- Standardize all unit test imports (conftest.py stubs all heavy deps; tests use `from scripts.ingest import ...`).
- TDD: `backend/tests/unit/test_ingest_artifacts.py` — covers save/load roundtrips, stop-after, start-from, missing artifact errors.

---

## ⏳ PHASE 9 — Pilot & Tuning

**Goal:** Real data is ingested, real mechanics onboarded, and thresholds are validated.

### ⏳ 9.1 Ingest Real Documents
- Run `ingest.py` against actual Komatsu PDF manuals locally.
- Verify each document appears in the admin Documents page with correct chunk_count and status `indexed`.
- Spot-check 5–10 queries against each document and review retrieval scores in Langfuse.

### ⏳ 9.2 Onboard Test Mechanics
- Invite 3–5 test mechanics to use the Telegram bot.
- Walk through the full `/start` → pending → approval → Mini App flow.
- Confirm they can select a machine model and submit queries.

### ⏳ 9.3 Threshold Validation
- Review Langfuse traces for the first 50 queries.
- If retrieval scores cluster differently than expected, adjust `RETRIEVAL_SCORE_THRESHOLD` and `RETRIEVAL_NO_ANSWER_THRESHOLD` in `.env` without code changes.
- Confirm no responses are returned without citations.

### ⏳ 9.4 Run Verification Plan
- Execute every test case from PRD §13 manually and document pass/fail.
- Fix any failures before considering the pilot complete.

### ⏳ 9.5 Monitoring Checklist
- Verify Langfuse dashboard shows traces for all queries.
- Verify Loguru logs are readable in `docker compose logs backend`.
- Verify admin `/stats` command in Telegram returns accurate numbers.

### ⏳ 9.6 Gemini 503 Retry in RAG Agent
- `ClassifierAgent` and `ResponderAgent` (Pydantic AI) call Gemini at query time and are currently unprotected against 503 UNAVAILABLE spikes.
- Add retry logic matching the ingest pipeline standard: 20 attempts, 2s flat wait, only on 503 errors.
- Apply to all Gemini call sites used at inference time: `classifier.py`, `responder.py`, and `embedder.py` (OpenRouter may also return 503).
- Ensure retries are transparent to the SSE stream — the client should not receive a partial or error response due to a transient API spike.

**Phase 9 Done When:** All PRD §13 verification tests pass; at least 50 real queries have been processed without hallucinations or missing citations.

---

## DEPENDENCIES BETWEEN PHASES

```
Phase 0 (scaffold)
  └─► Phase 1 (bot) — needs DB + config
  └─► Phase 2 (ingestion) — needs DB + config + R2
        └─► Phase 3 (retrieval) — needs populated chunks table
              └─► Phase 4 (LLM plane) — needs retrieval results
                    └─► Phase 5 (API) — needs all services
                          ├─► Phase 6 (Mini App) — needs API
                          └─► Phase 7 (Admin UI) — needs API
                                └─► Phase 8 (infra) — needs everything built
                                      └─► Phase 9 (pilot)
```

Phases 6 and 7 can be developed in parallel once Phase 5 is complete.
Phase 2 (ingestion) can be developed in parallel with Phase 1 (bot) once Phase 0 is done.

---

## CRITICAL CONSTRAINTS (never violate)

1. **No raw SQL** — all queries through SQLAlchemy ORM except Alembic migration files.
2. **No PDF storage on VPS** — `ingest.py` is the only pipeline; VPS receives only vectors and metadata.
3. **No hallucination** — system prompt grounding is non-negotiable; never soften it.
4. **No secrets in code** — all secrets via env vars; `.env` never committed.
5. **Russian UI** — every string visible to mechanics or in bot messages must be in Russian.
6. **HMAC validation** — Telegram initData must be cryptographically validated before any JWT is issued.
7. **Rate limiting** — Redis-based 15 req/min per user enforced at the API layer, not the agent layer.
8. **Input sanitization** — sanitize all text inputs at API boundary before passing to services.
