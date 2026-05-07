---
type: architecture
zone: architecture
last_updated: 2026-05-07
source_files:
  - docker-compose.yml
  - docker-compose.prod.yml
  - .env.example
  - docs/ADR_001.txt
  - README.md
related:
  - "[[index]]"
---

# Architecture Overview

Matsu Shi is an industrial machinery diagnostic chatbot designed specifically for Komatsu mechanics. It operates as a hybrid system comprising a **Telegram Bot** (for notifications and quick commands) and a **Telegram Mini App** (for rich diagnostic interactions).

## System Components

The system follows a microservices architecture managed via Docker Compose, consisting of six primary services:

1.  **Backend (FastAPI) & Telegram Bot**: The brain of the system. It handles the [[rag-pipeline]], agent orchestration, and provides REST/SSE endpoints. It also hosts the `aiogram` Telegram Bot, which handles user registration via a 5-step FSM.
2.  **Frontend (Telegram Mini App)**: A React-based SPA that provides a modern chat interface with support for streaming responses and session management.
3.  **Admin Dashboard**: A separate React SPA for administrators to manage users (approve/deny), monitor system stats, and oversee ingested documents.
4.  **PostgreSQL (pgvector)**: Stores relational data (users, sessions, feedback) and high-density vector embeddings for semantic search.
5.  **Redis**: Used for rate limiting (per-user) and caching to ensure system stability.
6.  **Nginx**: Acts as the reverse proxy and SSL termination point (via Certbot) in production.

## Key Architectural Decisions (ADR_001)

### Control Plane vs Data Plane
We decouple the system into two distinct planes to ensure reliability:
- **Control Plane ([[agents]])**: Powered by **PydanticAI**, enforcing strict type safety and structured outputs. The LLM is treated as a typed function.
- **Data Plane ([[rag-pipeline]])**: Powered by **LlamaIndex**, specialized in high-density technical data ingestion (PDFs, metadata).

### Stateful Diagnostic Workflows
Unlike stateless LLM wrappers, Matsu Shi maintains an **Active Diagnostic State**. Complex queries trigger a "Step-by-Step" mode, generating a diagnostic roadmap that persists across sessions.

## Data Flow: User Query

1.  **User Input**: User sends a message via the Telegram Mini App.
2.  **API Entry**: The `backend` receives the request via `/api/chat/`.
3.  **Classification**: The [[agents]] classify the query (e.g., diagnostic, general, or registration-related).
4.  **Retrieval**: If diagnostic, the [[rag-pipeline]] performs a hybrid search (Dense + Sparse) in PostgreSQL.
5.  **Reranking**: Retrieved chunks are reranked using Jina AI to ensure relevance.
6.  **Generation**: The responder agent constructs a structured answer using the retrieved context.
7.  **Streaming**: The response is streamed back to the frontend via SSE (Server-Sent Events).

## Environment & Topology

| Feature | Development | Production |
| :--- | :--- | :--- |
| **Bot Connection** | Long Polling | Webhooks (`/webhook/telegram`) |
| **Backend** | Uvicorn with `--reload` | Gunicorn/Uvicorn (multi-worker) |
| **Frontend/Admin** | Vite Dev Server | Nginx Static Serving |
| **SSL** | None | Let's Encrypt (Certbot) |
| **Migrations** | Manual (`alembic upgrade head`) | Automatic on startup |

## Control Mechanisms

- **Retrieval Thresholds**: Controlled via `RETRIEVAL_SCORE_THRESHOLD`. Queries below this threshold trigger an escalation path or clarification request instead of hallucinating.
- **Rate Limiting**: Redis-based limits enforced at the API layer to prevent resource exhaustion.
- **Observability**: All agent traces and RAG metrics are exported to [[langfuse]] for quality monitoring.

> ⚠️ Known issue: Nginx configuration currently requires manual domain updates in `docker/nginx/nginx.prod.conf` before deployment.
