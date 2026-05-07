---
type: component
zone: backend
last_updated: 2026-05-07
source_files:
  - backend/app/models/user.py
  - backend/app/models/session.py
  - backend/app/models/query.py
  - backend/app/models/chunk.py
  - backend/app/models/document.py
  - backend/app/core/database.py
  - backend/alembic/versions/0001_initial_schema.py
related:
  - "[[overview]]"
  - "[[rag-pipeline]]"
---

# Database

Matsu Shi uses **PostgreSQL** with the **pgvector** extension for both relational data and semantic vector storage. All database interactions are performed asynchronously using **SQLAlchemy 2.0**.

## Schema Overview

The database consists of 7 primary tables, organized around user management, diagnostic sessions, and the RAG knowledge base.

### 1. User Management
- **`users`**: Stores Telegram-registered mechanics.
  - Fields: `id`, `telegram_user_id` (unique), `status` (pending | active | denied | banned), `full_name`, `country`, `city`, `email`, `phone`.
  - Auditing: `approved_at`, `approved_by`.
- **`admin_users`**: Stores credentials for the [[admin-dashboard]].
  - Fields: `username`, `password_hash` (bcrypt).

### 2. Diagnostics & History
- **`diagnostic_sessions`**: Tracks ongoing troubleshooting threads.
  - Fields: `id`, `user_id`, `machine_model`, `title`, `status` (active | paused | completed), `created_at`, `updated_at`.
- **`queries`**: Logs every interaction within a session.
  - Fields: `id`, `session_id`, `user_id`, `query_text`, `response_text`, `model_used`, `retrieval_score`, `latency_ms`.
  - RAG metadata: `query_class`, `retrieved_chunk_ids` (ARRAY), `no_answer`.
- **`feedback`**: Stores user ratings for queries.
  - Fields: `id`, `query_id` (unique), `user_id`, `rating` (1 for UP, -1 for DOWN), `created_at`.

### 3. Knowledge Base (RAG)
- **`documents`**: Metadata for ingested PDF manuals.
  - Fields: `id`, `original_filename`, `display_name`, `machine_model`, `category`, `page_count`, `chunk_count`, `checksum` (SHA256 for deduplication).
- **`chunks`**: The granular content used for retrieval.
  - Fields: `id`, `document_id` (CASCADE delete), `chunk_index`, `content`, `chunk_type` (text | table | visual_caption), `section_title`, `page_number`, `machine_model`, `visual_refs` (ARRAY of R2 URLs), `token_count`.
  - **Vector**: `embedding` column using `Vector(1024)` for cosine similarity search.

## Vector Search (pgvector)

The `chunks` table uses the **pgvector** extension to perform semantic search.
- **Index Type**: HNSW (Hierarchical Navigable Small World) is used in production for fast approximate nearest neighbor search.
- **Distance Metric**: Cosine Distance (`1 - (embedding <=> query_vector)`).
- **Dimensions**: 1024 (matching `qwen3-embedding-4b`).

## Migrations (Alembic)

Database changes are managed via Alembic. Key migrations:
- `0001_initial_schema`: Core table definitions and initial indexes.
- `0002_user_registration_fields`: Added extended PII fields for mechanic registration.
- `0003_users_cascade_delete`: Ensures that deleting a user or document cleans up all related sessions and chunks.

## Database Setup (Core)

- **Engine**: `create_async_engine` using `asyncpg` driver.
- **Session**: `AsyncSessionLocal` factory with `expire_on_commit=False`.
- **Dependency**: `get_db()` provides an async session for FastAPI endpoints.

> ⚠️ Known issue: The `EMBED_DIM` is set at the ORM level via environment variable. Changing this requires a manual database migration to resize the `embedding` column.
