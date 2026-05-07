# Bootstrap Instructions

**For the compilation agent (OpenCode or similar). Run once to build the initial wiki from the codebase.**

Read this file fully before starting. Work through zones in order. After all zones, finalize index.md and log.md.

---

## Your Role

You are building the initial knowledge base for the Matsu Shi project. The owner works exclusively through LLM agents and has lost familiarity with the codebase. Your output is the primary source of truth for all future dev sessions.

Rules:
- Read SCHEMA.md before doing anything else
- Be descriptive, not prescriptive — document what IS, flag debt with `> ⚠️ Known issue:`
- Prefer code paths over prose: `backend/app/rag/retriever.py:dense_search()` beats "the dense search function"
- Use `[[WikiLinks]]` for every cross-reference between pages
- Do not speculate — only write what you can verify from source files

---

## Before You Start

1. Read `wiki/SCHEMA.md` in full
2. Run `git log --oneline -20` to understand recent activity
3. Run `git ls-files | head -100` to get a feel for the repo shape
4. Note the directory structure at top 3 levels

---

## Zone 1 — Architecture Overview

**Output:** `wiki/architecture/overview.md`

Files to read:
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `.env.example`
- `docs/ADR_001.txt`
- `README.md`

Write a page covering:
- What the system is (industrial machinery diagnostic chatbot via Telegram)
- The six services and how they connect (backend, bot, frontend, admin, postgres, redis, nginx)
- The control plane / data plane split (from ADR_001)
- How a user query flows end-to-end through the system
- Key environment variables and what they control
- Dev vs prod topology differences

---

## Zone 2 — RAG Pipeline

**Output:** `wiki/backend/rag-pipeline.md`

Files to read:
- `backend/app/rag/` — all files
- `backend/scripts/ingest.py`
- `ingest_wiki.md`

Write a page covering:
- The 6 ingest stages: Parse (Docling) → Visual (Gemini Vision) → Chunk → Enrich → Embed → Write
- The retrieval pipeline: dense (pgvector HNSW) + sparse (BM25) + Jina reranker
- Checkpoint/artifact caching logic in ingest
- Key thresholds: RETRIEVAL_SCORE_THRESHOLD, RETRIEVAL_NO_ANSWER_THRESHOLD
- Where images go (Cloudflare R2) and how captions are stored
- SSH tunnel setup for local ingest → VPS write

---

## Zone 3 — Agent Orchestration

**Output:** `wiki/backend/agents.md`

Files to read:
- `backend/app/agent/` — all files
- `backend/app/schemas/` — all files

Write a page covering:
- The agent pipeline: classifier → router → responder
- How Pydantic AI is used for structured outputs
- What the classifier decides and how
- How the responder constructs answers from retrieved chunks
- Structured output schemas and what they enforce
- Which models are used (from OpenRouter) and for what

---

## Zone 4 — API Layer

**Output:** `wiki/backend/api.md`

Files to read:
- `backend/app/api/` — all files
- `backend/app/core/config.py`
- `backend/app/core/security.py` (if exists)
- `backend/app/main.py`

Write a page covering:
- All API endpoints: path, method, auth requirement, purpose
- JWT flow: how tokens are issued and validated
- Telegram HMAC validation (where and how)
- Rate limiting (Redis-based, limits per user)
- CORS and middleware setup
- SSE streaming endpoint — how it works

---

## Zone 5 — Telegram Bot

**Output:** `wiki/backend/bot.md`

Files to read:
- `backend/app/bot/` — all files
- `backend/app/services/` — all files

Write a page covering:
- Bot command handlers and their purpose
- The 5-step registration FSM (states, transitions, what data is collected)
- Admin approval flow (how a pending user becomes active)
- How the bot interacts with the API (direct service calls vs HTTP)
- Webhook vs polling setup

---

## Zone 6 — Database

**Output:** `wiki/backend/database.md`

Files to read:
- `backend/app/models/` — all files
- `backend/alembic/versions/` — the most recent 2-3 migration files
- `backend/app/core/` — config and any DB setup files

Write a page covering:
- All tables: columns, types, constraints, indexes
- pgvector: which column, which index type (HNSW), dimensions
- Key relationships between tables (users → sessions → queries → feedback)
- Alembic migration naming convention and how to run migrations
- Async session setup and connection pooling

---

## Zone 7 — Frontend (Telegram Mini App)

**Output:** `wiki/frontend/mini-app.md`

Files to read:
- `frontend/src/store/` — all files
- `frontend/src/api/` — all files
- `frontend/src/hooks/` — all files
- `frontend/src/components/Chat/` — all files
- `frontend/src/components/Sidebar/` — all files
- `frontend/src/types/` — all files

Write a page covering:
- Zustand store structure: what state lives where
- SSE streaming: how messages stream to the UI (useSSE hook)
- JWT auth flow in the frontend (where token comes from, how it's sent)
- Session management: creating, switching, loading sessions
- Telegram Mini App SDK integration: what's used and why

---

## Zone 8 — Admin Dashboard

**Output:** `wiki/frontend/admin-dashboard.md`

Files to read:
- `admin-frontend/src/pages/` — all files
- `admin-frontend/src/api/` — all files
- `admin-frontend/src/store/` — all files

Write a page covering:
- What admin pages exist and what each does
- Admin auth (separate from user JWT — how does it work?)
- User management actions: approve, deny, ban, delete, message
- Document management: what can admin do with ingested docs
- Query/feedback visibility

---

## Zone 9 — Infrastructure

**Output:** `wiki/infrastructure/docker.md`

Files to read:
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `docker-compose.override.yml` (if exists)
- `docker/` — all files (nginx config)
- `backend/Dockerfile`
- `backend/Dockerfile.prod` (if exists)
- `frontend/Dockerfile`
- `admin-frontend/Dockerfile`

Write a page covering:
- All services in Compose and their roles
- Nginx routing: which path goes to which upstream, how /admin/ is handled
- Dev vs prod differences (hot reload, built images, SSL)
- How SSL/certbot is set up
- Volume mounts and what persists
- Common docker compose commands for this project

---

## Zone 10 — Integrations

**Output files:** one page per integration in `wiki/integrations/`

- `wiki/integrations/openrouter.md` — which models, how called, fallback logic
- `wiki/integrations/langfuse.md` — what is traced, how to read traces, key metrics
- `wiki/integrations/cloudflare-r2.md` — bucket structure, how images are stored/retrieved
- `wiki/integrations/jina.md` — reranker: when called, input/output format

Files to read for each: grep for the integration name across `backend/app/` to find all usages.

---

## Zone 11 — Procedures

**Output files:**
- `wiki/procedures/ingest.md` — step-by-step document ingestion (local machine → VPS)
- `wiki/procedures/deploy.md` — how to deploy to Hetzner VPS
- `wiki/procedures/monitoring.md` — Langfuse dashboard, log reading, /stats command

Files to read:
- `README.md` (deploy/ingest sections)
- `backend/scripts/` — all files
- `ingest_wiki.md`
- `docker-compose.prod.yml`

---

## Zone 12 — Evaluation & RAG Quality

**Output:** `wiki/evaluation/rag-metrics.md`

Files to read:
- `backend/tests/rag/` — if exists
- `ingest_wiki.md` (evaluation section)
- Search for "score", "threshold", "relevant" in backend code

Write a page covering:
- How RAG quality is measured
- Golden dataset structure (if any)
- Recent evaluation results or known weak points
- Which metrics are tracked in Langfuse

---

## Zone 13 — Security & Compliance

**Output:** `wiki/security/overview.md`

Files to read:
- `backend/app/core/security.py`
- `backend/app/api/deps.py`
- `docker/nginx.conf`
- Search for "HMAC", "JWT", "CORS"

Write a page covering:
- How Telegram HMAC is validated
- JWT issuance and rotation
- PII handling (what is stored, where)
- Rate limiting and DDoS protection strategy

---

## After All Zones

### Update index.md

Replace the "Awaiting bootstrap" placeholder in `wiki/index.md`:

1. **System Overview section** (top, under the header): Write a 30-50 line summary:
   - What Matsu Shi is
   - The six-service architecture
   - The RAG pipeline in 4 sentences
   - The agent pipeline in 2 sentences
   - Current phase (check Roadmap.md for active phase)
   - Any critical known issues you noticed during reading

2. **Page Catalog section**: Add one line per page you created:
   ```
   - [[overview]] — system architecture, services, data flow (architecture)
   - [[rag-pipeline]] — 6-stage ingest + retrieval pipeline with pgvector + Jina (backend)
   ... etc
   ```

### Update log.md

Append an entry:
```markdown
## [YYYY-MM-DD] bootstrap | Initial codebase analysis

- Files updated: list all wiki pages created
- Raw sources consumed: none (direct code reading)
- Notes: any contradictions found, any areas with insufficient documentation, any debt worth flagging
```

---

## Quality Check Before Finishing

- [ ] Every page has YAML frontmatter with `source_files` filled in
- [ ] Every page has at least 2 `[[WikiLinks]]` to other pages
- [ ] `index.md` System Overview is complete (not placeholder)
- [ ] `index.md` Page Catalog lists all created pages
- [ ] `log.md` has the bootstrap entry
- [ ] Any `> ⚠️ Known issue:` notes are specific and actionable
