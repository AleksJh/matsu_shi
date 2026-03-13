# Matsu Shi — Product Requirements Document
> Version: 1.1 | Status: Draft | Date: 2026-02-28

---

## 1. PROJECT IDENTITY

| Field | Value |
|---|---|
| Project Name | Matsu Shi |
| Client | Komatsu (internal, non-monetized) |
| Interface | Telegram Mini App + Telegram Bot |
| Language | Russian (all UI, responses, prompts, logs) |
| MVP Users | 1–20 mechanics + 1 Admin |
| Repo | Private GitHub monorepo `matsu-shi` |

---

## 2. ROLES & ACCESS CONTROL

| Role | Entry | Capabilities |
|---|---|---|
| **Mechanic** | `/start` → pending → Admin approves | Chat, session history (left sidebar), feedback (up/down) |
| **Admin** | Telegram bot commands + Web Dashboard | Approve/deny/ban users, manage documents, view query logs, system metrics, broadcast |

**Auth Flow (Mechanic):**
1. `/start` → bot records `telegram_user_id`, `username`, `first_name` → status = `pending`
2. Admin receives Telegram notification + inline buttons: `✅ Approve` / `❌ Deny`
3. Approve → status = `active`, mechanic receives confirmation, Mini App unlocked
4. Deny → status = `denied`, mechanic receives rejection
5. Admin can `ban` any active user at any time → immediate revocation

---

## 3. USER STORIES

| ID | Actor | Story |
|---|---|---|
| US-01 | Mechanic | Select machine model at start of conversation, then submit text query (error code, symptom) → receive structured repair guidance with citations |
| US-02 | Mechanic | View conversation history in left sidebar (current and past diagnostic sessions) |
| US-03 | Mechanic | Rate each response: thumbs up / thumbs down (once per response) |
| US-04 | Mechanic | See source citation per factual statement: `[Doc | Section | Page | Figure]` |
| US-05 | Mechanic | Receive "Информация не найдена. Попробуйте добавить конкретику в запрос." when no relevant data found |
| US-06 | Mechanic | Resume a paused diagnostic session from sidebar without losing progress |
| US-07 | Admin | Receive access request in Telegram → approve/deny with one tap |
| US-08 | Admin | View/manage users (pending/active/denied/banned) in web dashboard |
| US-09 | Admin | View full query log (text, response, score, model, feedback) in web dashboard |
| US-10 | Admin | View system metrics: query count, model usage, avg retrieval score, feedback ratio |
| US-11 | Admin | View indexed documents with status and metadata in web dashboard |
| US-12 | Admin | Run PDF ingestion via CLI script locally (local-to-cloud pipeline) |
| US-13 | Admin | Broadcast message to all active mechanics via bot |

---

## 4. KNOWLEDGE BASE & DATA ARCHITECTURE

### 4.1 PDF Ingestion Strategy: Local-to-Cloud

Processing (Docling, Gemini calls, embedding) is performed **on the developer's local machine** to minimize VPS load. The VPS never stores raw PDF files. Results are pushed directly to remote infrastructure:
- Vectors + text → PostgreSQL on Hetzner VPS (over network)
- Images (WebP) → Cloudflare R2

```bash
# Run locally on developer's machine:
python scripts/ingest.py --path ./manuals/PC300-8.pdf --machine-model "PC300-8" [--category "hydraulics"]
python scripts/ingest.py --dir ./manuals/ [--rebuild-index]
```

**Flags:**
- `--rebuild-index` — drops existing chunks for the document (by checksum) and re-indexes
- `--dry-run` — parse and chunk only, no writes

**Step-by-step pipeline:**

```
PDF File (local disk)
  │
  ▼
[1. DOCLING PARSE]
  Docling (IBM) → Markdown output
  - Preserves heading hierarchy (H1–H4)
  - Extracts tables as Markdown tables
  - Detects figure/image positions → records page_number + bounding_box
  - Outputs: markdown text + page metadata

  │
  ▼
[2. VISUAL INGESTION — PARALLEL with step 3]
  For each page containing a diagram/drawing/schematic:
  - Render page → WebP image (DPI=150)
  - Upload to Cloudflare R2: {machine_model}/{doc_name}/page_{n}.webp
  - Send WebP to Gemini 3 Flash (vision):
      Prompt: "Опиши техническую схему: компоненты, стрелки, метки.
               Одна строка технического описания на русском."
  - Store visual_tag: { page_number, r2_url, description }

  │
  ▼
[3. CHUNKING — see Section 4.2]

  │
  ▼
[4. CONTEXTUAL ENRICHMENT (text and visual_caption chunks only)]
  For each non-table chunk, send to Gemini 3 Flash:
    Prompt: "Напиши одно предложение, описывающее содержание этого фрагмента
             в контексте документа '{doc_name}' модели '{machine_model}'."
  Prepend to chunk: "[Контекст: {summary}]\n\n{original_text}"
  Table chunks: use the Gemini-generated context header from Rule 2 instead.

  │
  ▼
[5. EMBEDDING]
  Model: qwen3-embedding-4b via OpenRouter API
  Input: enriched chunk content (string)
  Output: float vector (dimension confirmed at integration from OpenRouter spec)
  Apply to all chunks.

  │
  ▼
[6. REMOTE WRITE]
  - INSERT chunk rows + vectors → PostgreSQL on Hetzner (asyncpg over SSL)
  - UPSERT document record → PostgreSQL
  - WebP files already uploaded in step 2
  - Log: indexed {n} chunks, {m} images for {doc_name}
```

### 4.2 Chunking Strategy: Hybrid Structural & Semantic

**Rule 1 — Header-Aware Chunking (primary boundary)**
- Use H1–H4 heading hierarchy from Docling Markdown as natural chunk boundaries
- A logical section (e.g., "Замена масляного фильтра") is kept as one block or a set of tightly related sub-chunks
- Sequential procedural steps (Step 1…Step N) are never split across chunks

**Rule 2 — Table Isolation (inviolable)**
- Tables are NEVER split across chunk boundaries
- Each table → isolated chunk of type `table`
- Gemini 3 Flash generates a context header prepended to the table:
  `"Таблица спецификаций давления для модели PC200-8:\n\n{table_markdown}"`
- No additional enrichment pass (Rule 4) is applied to table chunks; the context header serves as enrichment

**Rule 3 — Visual-Link Metadata**
- Every text chunk referencing "Figure N", "Рис. N", "Схема N" is tagged with:
  `visual_refs: ["https://r2.{account}.r2.cloudflarestorage.com/{path}/page_{n}.webp"]`
- These URLs are returned in API responses for inline display in the Mini App
- A `visual_caption` chunk is created for each figure page using its Gemini description

**Rule 4 — Small Overlap (text chunks only)**
- 10% token overlap between adjacent text chunks
- Not applied to table or visual_caption chunks
- Ensures smooth context transitions at chunk boundaries

### 4.3 Metadata Schema per Chunk

```json
{
  "doc_id": "integer",
  "doc_name": "PC300-8 Shop Manual",
  "machine_model": "PC300-8",
  "category": "hydraulics",
  "section_title": "Hydraulic Pump Replacement",
  "page_number": 247,
  "chunk_index": 42,
  "chunk_type": "text | table | visual_caption",
  "visual_refs": ["https://r2.../PC300-8/PC300-8_Shop_Manual/page_247.webp"],
  "token_count": 480
}
```

### 4.4 Domain Separation (Metadata Filtering)

- Every new conversation starts with the mechanic selecting a machine model (e.g., "PC300-8", "D375A")
- `machine_model` is set at session start and applied as a pre-filter on all retrieval in that session
- Retrieval applies `WHERE machine_model = ?` before vector search
- Prevents cross-contamination (PC300 data returned for PC200 query)

---

## 5. RETRIEVAL STRATEGY

### 5.1 Embedding Model
- **Model**: `qwen3-embedding-4b` via OpenRouter API
- **Key**: `OPENROUTER_API_KEY`
- Used for: chunk indexing (local, during ingestion) + query embedding (VPS, at inference time)

### 5.2 Hybrid Retrieval Pipeline (per query)

```
Query Text + machine_model filter (mandatory)
  │
  ├─► [Dense]  Embed query → qwen3-embedding-4b (OpenRouter)
  │            → pgvector cosine search, pre-filtered by machine_model (top-20)
  │
  ├─► [Sparse] BM25 keyword search on chunk content,
  │            pre-filtered by machine_model (top-20)
  │
  ▼
Merge + deduplicate → top-40 candidates
  │
  ▼
Reranking: jina-reranker-v3 via Jina AI API → top-5 final chunks
  │
  ▼
max_retrieval_score = max cosine similarity score among top-5
  │
  ▼
Return top-5 chunks with full metadata (content, section, page, visual_refs)
```

### 5.3 Retrieval Score Thresholds

| Condition | Action |
|---|---|
| `max_retrieval_score ≥ 0.65` AND query = `simple` | Use gemini-2.5-flash-lite |
| `max_retrieval_score < 0.65` OR query = `complex` | Use gemini-3-flash-preview |
| `max_retrieval_score < 0.30` (no relevant chunks) | Skip LLM entirely → return "not found" message |

---

## 6. LLM CONTROL PLANE (Pydantic AI)

### 6.1 Models

| Role | Model | Provider |
|---|---|---|
| Primary (default) | `gemini-2.5-flash-lite` | Google AI Studio |
| Advanced / Step-by-Step | `gemini-3-flash-preview` | Google AI Studio |
| Visual description (ingestion) | `gemini-3-flash-preview` (vision) | Google AI Studio |
| Contextual enrichment (ingestion) | `gemini-3-flash-preview` | Google AI Studio |
| Query classification | `gemini-2.5-flash-lite` | Google AI Studio |

### 6.2 Model Routing Logic

```python
if max_retrieval_score < 0.65 or query_class == "complex":
    model = LLM_ADVANCED_MODEL   # gemini-3-flash-preview
else:
    model = LLM_LITE_MODEL       # gemini-2.5-flash-lite
```

**Query classification (ClassifierAgent, lite model):**
- `simple` = single error code lookup, direct spec query, single-system question
- `complex` = multi-step diagnosis, cross-system correlation, multi-error analysis

**Step-by-Step Mode (complex queries):**
- When `query_class == "complex"`, the agent transitions into iterative diagnostic mode
- Each reasoning step is a separate query record linked to a `diagnostic_session`
- Session persists in DB with status `active` or `paused`
- Mechanic can leave and resume from sidebar without losing progress
- Session is marked `completed` when mechanic closes it or explicitly resolves the issue

### 6.3 System Prompt (Russian, enforced grounding)

```
Ты — технический ассистент механиков Komatsu. Отвечай ТОЛЬКО на основе
предоставленного контекста из технических мануалов.

Правила:
1. Каждое техническое утверждение ОБЯЗАТЕЛЬНО сопровождается ссылкой:
   [Документ: {doc_name} | Раздел: {section} | Стр. {page}]
2. Если в контексте нет ответа — строго отвечай:
   "Информация не найдена. Попробуйте добавить конкретику в запрос."
3. Никогда не домысливай. Никогда не используй знания вне контекста.
4. Структура ответа: Причина → Шаги устранения → Проверка → Цитаты.
5. Учитывай только данные модели техники, указанной в сессии.
```

### 6.4 Response Structure (Pydantic Output Schema)

```python
class Citation(BaseModel):
    doc_name: str
    section: str
    page: int
    visual_url: str | None        # Cloudflare R2 WebP URL, if applicable

class QueryResponse(BaseModel):
    answer: str                   # Structured markdown text
    citations: list[Citation]
    model_used: str               # "lite" | "advanced"
    retrieval_score: float
    query_class: str              # "simple" | "complex"
    no_answer: bool               # True when score < 0.30
    session_id: int | None        # Set for complex (Step-by-Step) queries
```

---

## 7. FUNCTIONAL REQUIREMENTS

### 7.1 Telegram Bot (aiogram 3.x)

| Trigger | Action |
|---|---|
| `/start` (new user) | Create `pending` user record, notify admin |
| `/start` (active user) | Send Mini App launch button (`WebAppButton`) |
| `/start` (denied/banned) | Inform user, no access granted |
| Admin: Approve button | status → `active`, notify mechanic |
| Admin: Deny button | status → `denied`, notify mechanic |
| Admin: Ban button | status → `banned`, notify mechanic |
| Admin: `/users` | List users by status with inline Approve/Deny/Ban actions |
| Admin: `/stats` | Queries today, active users, avg retrieval score |
| Admin: `/notify <text>` | Broadcast to all `active` users |

### 7.2 Telegram Mini App (React 18 + Tailwind)

**Layout:** Two-panel (desktop-like within Telegram WebView)
- **Left sidebar**: machine model selector (top) + conversation/session list
- **Main panel**: active chat

**Machine model selection:**
- Shown at the start of each new conversation (required before first message)
- Options rendered as a chip/button list from available indexed models
- Selected model is locked for the session duration and shown in the header

**Chat Message Components:**
- User bubble (right-aligned)
- Assistant bubble (left-aligned) containing:
  - Markdown-rendered response text
  - Citation block: `[PC300-8 Shop Manual | Hydraulic Pump | Стр. 247]`
  - Inline image viewer (WebP from R2) if `visual_url` present
  - Feedback row: 👍 / 👎 (one-time per message, disabled after vote)
  - Badge: "Расширенный анализ" — shown only when `model_used == "advanced"`

**Sidebar — Session List:**
- Lists all sessions (current session + past sessions with title = first query text truncated)
- Status badge: `active`, `paused`, `completed`
- Tap session → load full history for that session

**Technical:**
- Telegram WebApp JS SDK: `initData` extraction + theme tokens
- JWT obtained via `POST /api/v1/auth/telegram` (initData → HMAC validated → JWT)
- All API calls: `Authorization: Bearer <jwt>`
- `POST /api/v1/chat/query` → SSE stream for real-time response

### 7.3 Admin Web Dashboard (React 18 + Tailwind)

**Auth:** Username + bcrypt-hashed password → JWT (stored in admin_users table)

| Section | Content |
|---|---|
| **Users** | Table: Telegram username, name, status, registered_at, query_count. Actions: Approve/Deny/Ban |
| **Documents** | Table: name, machine_model, category, page_count, chunk_count, indexed_at, status |
| **Queries** | Paginated log: user, query text (truncated), model_used, retrieval_score, feedback, timestamp. Click → full detail modal |
| **System** | Daily query count chart, model usage pie chart, avg retrieval score trend, feedback ratio (up vs down) |

---

## 8. NON-FUNCTIONAL REQUIREMENTS

| Category | Requirement |
|---|---|
| **Hallucination** | 0% — system prompt + source grounding enforced unconditionally |
| **Citation** | 100% of factual statements cite `[doc \| section \| page]` |
| **Response latency** | P95 < 8s (lite model), P95 < 15s (advanced model) |
| **Availability** | 99% uptime (single VPS, Docker Compose) |
| **Security** | All secrets in env vars only. JWT for admin API. Telegram initData HMAC validation. Rate limit: 15 req/min per user (Redis). SQLAlchemy ORM (no raw SQL). Input sanitization on all text fields. |
| **Scale** | 1–20 concurrent users, no horizontal scaling for MVP |
| **Storage** | No PDF files on VPS disk. Ingestion is local (developer's machine) → vectors to PostgreSQL, images to Cloudflare R2. `ingest.py` is the sole data pipeline. |
| **Observability** | Langfuse (cloud): traces AI reasoning chains + RAG retrieval scores. Loguru: structured system event logging to stdout. PostgreSQL stores only final query records and audit trails. |
| **Cost** | Minimize advanced model calls via routing. Monitor Google AI Studio + OpenRouter + Jina AI quotas. |

---

## 9. SYSTEM ARCHITECTURE

### 9.1 Monorepo Structure

```
matsu-shi/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers: chat, admin, auth, webhook
│   │   ├── core/           # Config (pydantic-settings), security (JWT), logging (Loguru)
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── rag/            # LlamaIndex: retrieval, reranking (Jina), BM25
│   │   ├── agent/          # Pydantic AI: ClassifierAgent, ResponderAgent, Router
│   │   ├── bot/            # aiogram 3.x: mechanic handlers, admin handlers
│   │   └── services/       # UserService, QueryService, SessionService, FeedbackService
│   ├── scripts/
│   │   └── ingest.py       # LOCAL CLI: PDF ingestion pipeline (run on developer machine)
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── alembic/            # DB migrations
│   ├── pyproject.toml      # uv-managed dependencies
│   └── Dockerfile
├── frontend/               # Telegram Mini App
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar/        # SessionList, MachineModelSelector
│   │   │   └── Chat/           # MessageBubble, CitationBlock, FeedbackButtons, ImageViewer
│   │   ├── hooks/              # useChat, useSessions, useTelegramAuth, useSSE
│   │   ├── api/                # Axios client, typed API calls
│   │   └── store/              # Zustand: auth, active session, messages
│   ├── package.json
│   └── Dockerfile
├── admin-frontend/         # Admin dashboard
│   ├── src/
│   │   ├── pages/          # UsersPage, DocumentsPage, QueriesPage, SystemPage
│   │   ├── components/
│   │   └── api/
│   ├── package.json
│   └── Dockerfile
├── docker/
│   └── nginx/nginx.conf
├── docker-compose.yml      # Development
├── docker-compose.prod.yml # Production (SSL volumes, restart policies)
├── .env.example
└── README.md
```

### 9.2 Docker Compose Services

| Service | Image | Description |
|---|---|---|
| `backend` | Python 3.13 custom | FastAPI + aiogram webhook |
| `frontend` | Node build + nginx | Telegram Mini App static files |
| `admin` | Node build + nginx | Admin dashboard static files |
| `postgres` | postgres:16-pgvector | Main database |
| `redis` | redis:7-alpine | Rate limiting + caching |
| `nginx` | nginx:alpine | Reverse proxy + SSL termination |

Note: `ingest.py` runs on the developer's local machine, not inside Docker. It connects to the remote PostgreSQL via `DATABASE_URL` and to R2 via `CF_R2_*` env vars.

### 9.3 PostgreSQL Schema

```sql
-- Users
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|active|denied|banned
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    approved_by VARCHAR(255)
);

-- Documents (metadata only — no PDFs stored on server)
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    original_filename VARCHAR(500) NOT NULL,
    display_name VARCHAR(500) NOT NULL,
    machine_model VARCHAR(255) NOT NULL,
    category VARCHAR(255),
    page_count INT,
    chunk_count INT,
    status VARCHAR(20) DEFAULT 'indexed',  -- indexed|error|processing
    indexed_at TIMESTAMPTZ DEFAULT NOW(),
    checksum VARCHAR(64) UNIQUE            -- SHA-256 of original PDF, prevents re-indexing
);

-- Chunks
CREATE TABLE chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,               -- enriched: "[Контекст: ...]\n\noriginal text"
    chunk_type VARCHAR(20) DEFAULT 'text',  -- text|table|visual_caption
    section_title VARCHAR(500),
    page_number INT,
    machine_model VARCHAR(255),          -- denormalized for fast metadata pre-filter
    visual_refs TEXT[],                  -- array of Cloudflare R2 WebP URLs
    embedding vector(EMBED_DIM),         -- qwen3-embedding-4b; confirm dim at integration
    token_count INT
);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_machine_model_idx ON chunks (machine_model);

-- Diagnostic Sessions
CREATE TABLE diagnostic_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    machine_model VARCHAR(255) NOT NULL,
    title VARCHAR(500),                  -- first query text (truncated to 100 chars)
    status VARCHAR(20) DEFAULT 'active', -- active|paused|completed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Queries
CREATE TABLE queries (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT REFERENCES diagnostic_sessions(id),
    user_id BIGINT REFERENCES users(id),
    query_text TEXT NOT NULL,
    response_text TEXT,
    model_used VARCHAR(20),              -- "lite" | "advanced"
    retrieval_score FLOAT,
    query_class VARCHAR(20),             -- "simple" | "complex"
    retrieved_chunk_ids BIGINT[],
    no_answer BOOLEAN DEFAULT FALSE,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback
CREATE TABLE feedback (
    id BIGSERIAL PRIMARY KEY,
    query_id BIGINT REFERENCES queries(id) UNIQUE,
    user_id BIGINT REFERENCES users(id),
    rating SMALLINT NOT NULL,            -- 1 (thumbs up) | -1 (thumbs down)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin Users (web dashboard login)
CREATE TABLE admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL  -- bcrypt
);
```

### 9.4 Key FastAPI Endpoints

```
POST   /webhook/telegram                    Telegram bot webhook (HMAC-validated)

POST   /api/v1/auth/telegram               Validate Telegram initData → return JWT
POST   /api/v1/auth/admin/login            Admin login (username+password) → return JWT

POST   /api/v1/chat/sessions               Create new diagnostic session
GET    /api/v1/chat/sessions               List user's sessions (for sidebar)
PUT    /api/v1/chat/sessions/{id}/status   Update session status (paused|completed)

POST   /api/v1/chat/query                  SSE stream: submit query, receive response
GET    /api/v1/chat/sessions/{id}/history  Full message history for a session

POST   /api/v1/feedback/{query_id}         Submit thumbs up/down

GET    /api/v1/admin/users                 List users (filter by status, pagination)
PUT    /api/v1/admin/users/{id}/status     Update: active|denied|banned
GET    /api/v1/admin/documents             List indexed documents
GET    /api/v1/admin/queries               Paginated query log (filter by user, date, model)
GET    /api/v1/admin/queries/{id}          Full query detail modal
GET    /api/v1/admin/stats                 Aggregated system metrics
POST   /api/v1/admin/broadcast             Broadcast to all active users via bot
```

### 9.5 Query Processing Data Flow

```
Mini App → POST /api/v1/chat/query
  Body: { session_id, query_text }
  Header: Authorization: Bearer <jwt>
  │
  ├── JWT validation
  ├── Rate limit check (Redis: 15 req/min per user_id → HTTP 429 if exceeded)
  ├── User status check → HTTP 403 if not active
  ├── Load session (machine_model filter from session record)
  │
  ▼
QueryService.process(session_id, user_id, query_text, machine_model)
  │
  ├── [LlamaIndex RAG]
  │     1. Embed query → qwen3-embedding-4b (OpenRouter)
  │     2. Dense: pgvector cosine + WHERE machine_model = ? → top-20
  │     3. Sparse: BM25 + WHERE machine_model = ? → top-20
  │     4. Merge + dedup → top-40
  │     5. Jina reranker-v3 → top-5
  │     6. max_retrieval_score = max(cosine scores)
  │     7. If max_score < 0.30 → skip LLM, return "not found" immediately
  │
  ├── [Pydantic AI Control Plane]
  │     1. ClassifierAgent (gemini-2.5-flash-lite): query_class = simple|complex
  │     2. Route: score < 0.65 OR complex → gemini-3-flash-preview
  │     3. ResponderAgent (selected model):
  │           - System prompt (Russian, strict grounding)
  │           - Context: top-5 enriched chunks + metadata + visual_refs
  │           - Structured output: QueryResponse
  │
  ├── [Langfuse] Trace: retrieval_score, model_used, query_class, latency
  ├── Stream response via SSE
  └── Store query record (async, after stream completes)
```

---

## 10. REQUIRED ACCOUNTS & API KEYS

| # | Service | What to Create | Env Var(s) |
|---|---|---|---|
| 1 | **Telegram / BotFather** | Create bot → get token. Enable Web App (set Mini App URL). | `BOT_TOKEN` |
| 2 | **Google AI Studio** | Create API key | `GEMINI_API_KEY` |
| 3 | **OpenRouter** | Create account + API key | `OPENROUTER_API_KEY` |
| 4 | **Jina AI** | Create account + API key | `JINA_API_KEY` |
| 5 | **Cloudflare** | Create account + R2 bucket `matsu-shi-images` + R2 API token | `CF_R2_ENDPOINT`, `CF_R2_ACCESS_KEY_ID`, `CF_R2_SECRET_ACCESS_KEY`, `CF_R2_BUCKET`, `CF_R2_PUBLIC_BASE_URL` |
| 6 | **Langfuse** | Create account (cloud) + project → get public/secret keys | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |
| 7 | **GitHub** | Create private repo `matsu-shi` | — |
| 8 | **Hetzner** | Create account + VPS CX31 (4 vCPU, 8GB RAM, 80GB SSD) + SSH key | — |
| 9 | **Domain registrar** | Buy domain, point A record to Hetzner VPS IP | `APP_BASE_URL` |
| 10 | **Let's Encrypt** | SSL via certbot on VPS (free) | — |

**Environment Variables (.env):**
```env
# Telegram
BOT_TOKEN=
ADMIN_TELEGRAM_ID=              # Integer: your personal Telegram user_id

# Google AI
GEMINI_API_KEY=
LLM_LITE_MODEL=gemini-2.5-flash-lite
LLM_ADVANCED_MODEL=gemini-3-flash-preview

# OpenRouter (embeddings)
OPENROUTER_API_KEY=
EMBED_MODEL=qwen3-embedding-4b

# Jina AI (reranking)
JINA_API_KEY=
RERANKER_MODEL=jina-reranker-v3

# Cloudflare R2
CF_R2_ENDPOINT=                 # https://<account_id>.r2.cloudflarestorage.com
CF_R2_ACCESS_KEY_ID=
CF_R2_SECRET_ACCESS_KEY=
CF_R2_BUCKET=matsu-shi-images
CF_R2_PUBLIC_BASE_URL=          # Public read base URL

# Langfuse (observability)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@<hetzner_ip>:5432/matsu_shi

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=                     # openssl rand -hex 32
ADMIN_USERNAME=
ADMIN_PASSWORD_HASH=            # bcrypt hash

# App
APP_BASE_URL=https://yourdomain.com
ENVIRONMENT=production          # development | production

# RAG Thresholds
RETRIEVAL_SCORE_THRESHOLD=0.65
RETRIEVAL_NO_ANSWER_THRESHOLD=0.30
```

---

## 11. OUT OF SCOPE (MVP)

- Voice input/output
- Mechanic photo/image upload for diagnosis
- Offline mode
- Mobile native app
- Multi-language UI
- Multi-tenant architecture
- Celery async task queue
- Automatic PDF sync from external source
- Separate structured error code database (all via RAG from PDFs)
- Horizontal scaling / load balancing
- Self-hosted Langfuse (use cloud for MVP)

---

## 12. IMPLEMENTATION PHASES

| Phase | Description |
|---|---|
| **0 — Setup** | Monorepo structure, `pyproject.toml` (uv), Docker Compose (dev + prod), `.env.example`, Alembic initial migration (all tables) |
| **1 — Bot Auth** | aiogram 3.x: `/start` flow, pending→active state machine, admin inline buttons, `/users` `/stats` `/notify` |
| **2 — RAG Ingestion** | `ingest.py`: Docling parse → visual ingestion (Gemini + R2) → chunking (4 rules) → contextual enrichment → qwen3 embed → write to PostgreSQL |
| **3 — Retrieval** | Hybrid search (pgvector + BM25) → Jina reranking → score thresholds → machine_model filter |
| **4 — LLM Control Plane** | ClassifierAgent, ResponderAgent, routing logic, Step-by-Step session persistence, citation enforcement, "not found" fallback, Langfuse tracing |
| **5 — FastAPI Backend** | All endpoints, JWT middleware, rate limiting (Redis), SSE streaming, session management |
| **6 — Telegram Mini App** | React 18 + Tailwind + Vite, Telegram SDK, sidebar + chat layout, machine model selector, citations, image viewer, feedback |
| **7 — Admin Dashboard** | React 18 + Tailwind + Vite, JWT login, Users/Documents/Queries/System pages |
| **8 — Infrastructure** | Hetzner VPS setup, Docker Compose prod, nginx + Let's Encrypt, Telegram webhook registration, GitHub Actions CI (lint + tests) |
| **9 — Pilot** | Load real Komatsu PDFs locally via `ingest.py`, onboard 3–5 test mechanics, monitor Langfuse, tune thresholds |

---

## 13. VERIFICATION PLAN

| Test | Method |
|---|---|
| Auth flow | New user → `/start` → admin approves → Mini App accessible |
| Denied access | status `denied` → `/start` → rejection, no Mini App |
| Machine model selector | New session → model selector shown → selection locks for session |
| RAG accuracy | Query 10 known error codes → verify citations show correct document + page |
| Hallucination | Query topic absent from manuals → returns "Информация не найдена. Попробуйте добавить конкретику." |
| Visual chunks | Query about a figure → response `visual_url` populated → image shown in Mini App |
| Domain filter | PC300 query → no PC200 chunk data in response |
| LLM routing | Craft query with expected score < 0.65 → verify `model_used = "advanced"` in DB |
| Step-by-Step | Complex query → session persists → close app → reopen → session resumable from sidebar |
| Citation presence | All responses include `[doc \| section \| page]` block |
| Rate limiting | 16 requests in 60s → 16th returns HTTP 429 |
| Admin ban | Ban active user → next query returns HTTP 403 |
| Feedback | Submit 👎 → appears in Queries section of admin dashboard |
| Ingestion CLI | `ingest.py` on new PDF → document in admin Documents page → queryable |
| Docker restart | `docker compose down && up` → all data preserved (Postgres volume) |
| Telegram initData | Tampered initData → rejected with HTTP 401 |
| Langfuse | After query → trace visible in Langfuse dashboard with retrieval_score |
