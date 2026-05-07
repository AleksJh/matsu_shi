---
description: Load project context from the wiki before starting dev work
---

# /wiki-prime — Load Wiki Context

Replaces the old `/prime` command. Loads context from the living wiki instead of static docs.

## Steps

### 1. Always read this file

- `wiki/index.md` — system overview + catalog of all wiki pages

### 2. Identify relevant zones from the current task

Based on what the user is about to work on, determine which zones are involved:

| If the task touches... | Read this wiki page |
|------------------------|---------------------|
| RAG, retrieval, chunks, embeddings, reranking | `wiki/backend/rag-pipeline.md` |
| LLM agents, classifier, responder, structured output | `wiki/backend/agents.md` |
| FastAPI routes, JWT, endpoints | `wiki/backend/api.md` |
| Telegram bot, FSM, handlers | `wiki/backend/bot.md` |
| Database models, migrations, pgvector | `wiki/backend/database.md` |
| Auth, security, rate limiting | `wiki/backend/auth.md` |
| React Mini App, SSE streaming, Zustand | `wiki/frontend/mini-app.md` |
| Admin dashboard | `wiki/frontend/admin-dashboard.md` |
| Docker, Nginx, deploy, SSL | `wiki/infrastructure/docker.md` |
| OpenRouter, Langfuse, R2, Jina | relevant `wiki/integrations/*.md` |
| Ingestion pipeline, ingest.py | `wiki/procedures/ingest.md` |

If the task involves any external API or service, **always** read `wiki/integrations/list.md` or specific integration pages to check for known limits or auth patterns.

If no specific zone is clear yet, skip this step.

### 3. Output a context digest

Produce a brief summary (5-10 bullet points) of what you learned:
- What the system is
- Which components are relevant to the current task
- Any critical patterns or known issues that affect the work
- Current dev phase and active blockers (from `wiki/index.md` System Overview)

Keep it scannable. This digest orients you for the session — don't repeat it back to the user unless asked.

### 4. Note if wiki is unpopulated

If `wiki/index.md` System Overview section only contains the placeholder ("Awaiting bootstrap"), tell the user:
> "Wiki is empty — bootstrap hasn't been run yet. I'll work from codebase directly this session. Consider running the bootstrap via OpenCode when convenient."
Then proceed to read relevant source files directly as needed.
