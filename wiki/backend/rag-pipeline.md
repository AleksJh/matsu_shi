---
type: component
zone: backend
last_updated: 2026-05-07
source_files:
  - backend/app/rag/retriever.py
  - backend/app/rag/multi_retriever.py
  - backend/app/rag/embedder.py
  - backend/scripts/ingest.py
  - ingest_wiki.md
related:
  - "[[overview]]"
  - "[[database]]"
  - "[[agents]]"
---

# RAG Pipeline

The RAG (Retrieval-Augmented Generation) pipeline is the core of Matsu Shi's intelligence. It is divided into a **6-stage ingestion pipeline** (run locally) and a **hybrid retrieval pipeline** (run on the server).

## Ingestion Pipeline (Local)

Ingestion is performed locally by the developer to avoid exposing API keys on the VPS and to leverage local processing power for PDF parsing.

### 1. Parse (Docling)
- **Tool**: IBM Docling
- **Process**: Converts PDF to structured Markdown.
- **Reliability**: Large PDFs are split into 60-page chunks to prevent `std::bad_alloc` memory corruption in `pypdfium2`.
- **OCR**: Disabled (`do_ocr=False`) as Komatsu manuals are digital PDFs with text layers.

### 2. Visual Ingest (Gemini Vision)
- **Model**: `LLM_ADVANCED_MODEL` (Gemini 3 Flash Preview)
- **Process**: Renders figure pages to WebP (150 DPI) → Uploads to [[cloudflare-r2]] → Gemini generates a one-line Russian description of the diagram.
- **Output**: `VisualTag(page_number, r2_url, description)`.

### 3. Chunking (Rule-based)
- **Rule 1**: Structural splitting via Markdown headers (H1-H4).
- **Rule 2**: Tables are isolated into dedicated `table` chunks.
- **Rule 4**: 10% token overlap between adjacent text chunks.
- **Merging**: Chunks smaller than `CHUNK_MIN_TOKENS` (80) are merged into the preceding chunk to reduce noise.

### 4. Contextual Enrichment (Gemini Flash Lite)
- **Model**: `LLM_LITE_MODEL` (Gemini 2.5 Flash Lite)
- **Rule 3**: Attaches [[cloudflare-r2]] URLs to text chunks that reference "Figure/Рис./Схема N".
- **Visual Chunks**: Creates `visual_caption` chunks from visual descriptions.
- **Prepend**: Gemini generates a summary and prepends `[Контекст: ...]` to text/visual chunks and `[Таблица: ...]` to table chunks.

### 5. Embedding (OpenRouter)
- **Model**: `qwen3-embedding-4b`
- **Dimension**: 1024 (validated on first call).
- **Process**: Enriched content is converted to vectors and stored in `embedded.json`.

### 6. Write (VPS)
- **Process**: Bulk inserts data into [[database]] via an SSH tunnel.
- **Final State**: Document status updated to `indexed`.

## Retrieval Pipeline (Server)

The retrieval flow is optimized for accuracy and speed, using a hybrid approach.

1.  **Query Embedding**: Natural language query is converted to a vector using `embed_text`.
2.  **Parallel Search**:
    - **Dense Channel**: pgvector cosine distance search in [[database]].
    - **Sparse Channel**: PostgreSQL Full-Text Search (FTS) for exact keyword matching.
3.  **Early Exit**: If `max_score < RETRIEVAL_NO_ANSWER_THRESHOLD` (0.30), the pipeline returns a "no_answer" result immediately to save costs.
4.  **Merge & Dedup**: Candidates (up to 40) are merged and deduplicated by `chunk.id`, prioritizing dense results.
5.  **Reranking ([[jina]])**: All merged candidates (up to 40) are reranked using Jina Reranker v3.
6.  **Model Routing**:
    - `max_score < RETRIEVAL_SCORE_THRESHOLD` (0.65) **OR** `query_class == "complex"` → `LLM_ADVANCED_MODEL`.
    - Otherwise → `LLM_LITE_MODEL`.

## Failure Paths

### Embedding Failure
If the embedding service (OpenRouter) is unavailable after 20 retries (for 503 errors) or returns an error immediately, `embed_text` returns `None`. The pipeline then:
1.  Logs a warning.
2.  Returns a `RetrievalResult` with `no_answer=True` and `embed_failed=True`.
3.  Bypasses retrieval and reranking stages completely.

## Checkpoint System

The pipeline uses a SHA256-based caching system in `cache/{sha256}/`:
- **Artifacts**: `parse.json`, `visual.json`, `chunks.json`, `enriched.json`, `embedded.json`.
- **Resumability**: Use `--start-from {stage}` to resume a failed ingest. Partial progress is saved for `visual` and `enrich` stages (`visual_partial.json`, `enriched_partial.json`).

> ⚠️ Known issue: docling models (~40MB) are downloaded from `modelscope.cn` on the first run, requiring internet access.
