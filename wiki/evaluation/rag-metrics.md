---
type: architecture
zone: evaluation
last_updated: 2026-05-07
source_files:
  - backend/app/rag/retriever.py
  - backend/app/core/config.py
related:
  - "[[rag-pipeline]]"
  - "[[database]]"
  - "[[integrations]]"
---

# RAG Quality & Evaluation

Matsu Shi uses a tiered retrieval strategy and strict score thresholds to ensure that mechanics receive only accurate, grounded information from the technical manuals.

## Quality Thresholds

The system's behavior is governed by the `max_score` (the highest cosine similarity score from the dense retrieval channel).

| Score Range | Logic | Action |
| :--- | :--- | :--- |
| **0.00 - 0.29** | **Insufficient** | `no_answer = True`. Immediate response: "Информация не найдена". |
| **0.30 - 0.64** | **Mediocre** | Use `LLM_ADVANCED_MODEL`. Reranking is mandatory. |
| **0.65 - 1.00** | **High Confidence** | Use `LLM_LITE_MODEL` for speed. |

## Retrieval Optimizations

### 1. Hybrid Search
To handle both semantic meaning (vector search) and exact technical codes (keyword search), the system performs parallel retrieval:
- **Dense**: `pgvector` cosine similarity.
- **Sparse**: PostgreSQL Full-Text Search (FTS).
- **Merge**: Results are combined and deduplicated by `chunk_id`.

### 2. Cross-Encoder Reranking
Vector search (Bi-Encoders) is fast but can lose nuance. Matsu Shi uses **Jina Reranker v3** (a Cross-Encoder) to re-evaluate the top 40 candidates.
- **Top-N**: Only the final Top-10 chunks are passed to the LLM context.
- **Accuracy**: Reranking significantly reduces hallucinations when multiple manuals contain similar but distinct procedures.

### 3. Contextual Pre-processing
During ingestion, every chunk is "wrapped" in a summary:
- **Text Chunks**: Prepend `[Контекст: {summary}]`.
- **Table Chunks**: Prepend `[Таблица: {description}]`.
This enrichment ensures that the embedding vector captures the global purpose of the chunk, not just its local fragments.

## Monitoring Quality

Quality is audited in real-time via **Langfuse**:
- **Retrieval Scores**: Logged for every query to identify "dead zones" in the documentation.
- **Latency Tracking**: Monitors the performance impact of Jina reranking and model routing.
- **User Feedback**: Thumbs up/down ratings are correlated with retrieval scores to refine thresholds.

## Visual Accuracy

Visual retrieval (searching for diagrams) has a higher threshold:
- **Threshold**: `0.75` (configured via `VISUAL_MIN_SCORE`).
- **Goal**: Prevent the assistant from showing a wrong schematic, which could lead to incorrect repairs.

> 💡 Tip: If mechanics consistently report "Information not found" for existing parts, the `RETRIEVAL_NO_ANSWER_THRESHOLD` should be lowered slightly, or the ingestion pipeline should be re-run with smaller chunk sizes.
