---
type: architecture
zone: infrastructure
last_updated: 2026-05-07
source_files:
  - backend/app/core/config.py
  - backend/app/core/tracing.py
  - backend/app/rag/retriever.py
  - backend/scripts/ingest.py
related:
  - "[[overview]]"
  - "[[rag-pipeline]]"
  - "[[agents]]"
---

# External Integrations

Matsu Shi relies on a curated set of external APIs to provide state-of-the-art diagnostic capabilities while maintaining a lean local infrastructure.

## 1. OpenRouter (Intelligence Layer)
The system uses OpenRouter as a unified gateway for Large Language Models and Embeddings.

- **LLMs**:
  - `gemini-2.5-flash-lite`: Primary model for classification, reformulation, and simple queries.
  - `gemini-3-flash-preview`: Used for complex diagnostics and visual analysis.
- **Embeddings**:
  - `qwen3-embedding-4b`: Generates 1024-dimensional vectors for the knowledge base.
- **Reliability**: All calls implement a 20-retry policy with a 2-second flat wait to handle transient upstream availability issues.

## 2. Langfuse (Observability)
Every diagnostic query is traced using Langfuse for performance monitoring and hallucination auditing.

- **Trace Correlation**: The `trace_id` generated at the start of retrieval is carried through the entire pipeline, linking search results to the final LLM response.
- **Metadata**: Traces capture `retrieval_score`, `latency_ms`, and `model_used`.
- **Fault Tolerance**: Tracing is non-blocking; if Langfuse is unavailable, the system logs a warning and continues processing the query.

## 3. Cloudflare R2 (Visual Asset CDN)
Technical diagrams from manuals are extracted as WebP images and stored in an S3-compatible R2 bucket.

- **Upload Flow**: During ingestion, pages are rendered at 150 DPI and uploaded with a path structure: `{machine_model}/{doc_name}/page_{n}.webp`.
- **Retrieval**: The Mini App fetches these images directly via the `CF_R2_PUBLIC_BASE_URL`.
- **Optimization**: Images are converted to WebP to minimize bandwidth usage inside the Telegram interface.

## 4. Jina AI (Reranking)
To ensure the most relevant documentation reaches the LLM, a cross-encoder reranker is used.

- **Model**: `jina-reranker-v3`.
- **Process**: After merging Dense (Vector) and Sparse (FTS) search results, Jina reranks the top 40 candidates to select the final 10.
- **Cost Control**: Jina is bypassed if the initial vector similarity score is below the `RETRIEVAL_NO_ANSWER_THRESHOLD` (0.30).

## 5. Gemini Vision (Visual Enrichment)
During the ingestion process, Gemini Vision provides technical descriptions of diagrams.

- **Usage**: Descriptions are stored as `visual_caption` chunks in the [[database]].
- **Searchability**: These descriptions allow mechanics to find diagrams using natural language queries (e.g., "Схема гидрораспределителя").

## Configuration Summary

All API keys and endpoints are configured via the `.env` file and managed by Pydantic Settings in `backend/app/core/config.py`.

| Key | Variable | Service |
| :--- | :--- | :--- |
| **LLM Gateway** | `OPENROUTER_API_KEY` | OpenRouter |
| **Reranker** | `JINA_API_KEY` | Jina AI |
| **Tracing** | `LANGFUSE_SECRET_KEY` | Langfuse |
| **Storage** | `CF_R2_SECRET_ACCESS_KEY`| Cloudflare |
| **Direct AI** | `GEMINI_API_KEY` | Google AI Studio |
