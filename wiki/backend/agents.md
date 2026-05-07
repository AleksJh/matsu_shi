---
type: architecture
zone: backend
last_updated: 2026-05-07
source_files:
  - backend/app/agent/classifier.py
  - backend/app/agent/reformulator.py
  - backend/app/agent/responder.py
  - backend/app/agent/router.py
  - backend/app/agent/title_generator.py
  - backend/app/schemas/query.py
related:
  - "[[overview]]"
  - "[[rag-pipeline]]"
  - "[[api]]"
---

# Agent Orchestration

Matsu Shi uses a multi-agent system built on **Pydantic AI** to manage complex diagnostic workflows. The "Control Plane" orchestrates the interaction between the user, the retrieval system, and the generative models.

## Agent Pipeline

Every user query flows through a three-stage agent pipeline:

### 1. Classification ([[classifier.py]])
- **Model**: `LLM_LITE_MODEL` (Gemini 2.5 Flash Lite)
- **Output**: `ClassifierOutput` (simple | complex)
- **Logic**:
  - `simple`: Direct questions about specs, error codes, or single systems.
  - `complex`: Multi-step diagnostics, correlation of multiple systems, or follow-up questions in an existing session.
- **Context Awareness**: Prepend last 2 messages of history to ensure follow-up queries (e.g., "What about the valve?") are classified as `complex`.

### 2. Reformulation ([[reformulator.py]])
- **Model**: `LLM_LITE_MODEL`
- **Purpose**: Only triggered for `complex` queries or follow-ups.
- **Logic**: Analyzes the **full session history** to generate 1–3 standalone RAG queries. This ensures that keyword-dense search terms are extracted from vague follow-up questions.

### 3. Routing ([[router.py]])
- **Logic**: Selects the "Responder" model based on two factors:
  - **Advanced Model** (`gemini-3-flash-preview`): Used if `query_class == "complex"` OR `max_retrieval_score < 0.65`.
  - **Lite Model** (`gemini-2.5-flash-lite`): Used for `simple` queries with high-confidence retrieval.

### 4. Response Generation ([[responder.py]])
- **Model**: Dynamically selected via router.
- **Output**: `QueryResponse` (structured answer + citations).
- **Rules**:
  - **Bypass Rule**: If `retrieval_result.no_answer` is `True`, the LLM is bypassed, and a fixed string ("Информация не найдена...") is returned immediately.
  - **Citation Markers**: Must use `[N]` format linking to sources.
  - **Hallucination Guard**: Rule #2 mandates a fixed "Information not found" response if the context is irrelevant.
  - **Visual Integration**: Calls `retrieve_visual` to find high-confidence technical diagrams and attaches them to the first citation.

### 5. Title Generation ([[title_generator.py]])
- **Model**: `LLM_LITE_MODEL`
- **Purpose**: Auto-generates a short Russian session title (3-6 words) after the first query is answered.
- **Logic**: Uses the first Q&A pair to summarize the diagnostic topic. Falls back to a truncated query if the agent fails.

## Structured Schemas

The system enforces a strict contract via Pydantic models in `backend/app/schemas/query.py`:

- **[[Citation]]**:
  - `doc_name`, `section`, `page`, `visual_url` (Cloudflare R2 link).
- **[[QueryResponse]]**:
  - `answer`: Markdown response.
  - `citations`: List of used sources.
  - `model_used`: "lite" | "advanced".
  - `retrieval_score`: Max score from dense channel.
  - `no_answer`: Boolean flag indicating if LLM was bypassed or returned "not found".

## Model Fallbacks & Retries

All agents implement a standard retry pattern for Gemini API transient errors (503 UNAVAILABLE, 504 GATEWAY_TIMEOUT):
- **Retries**: 20 attempts.
- **Wait**: 2-second flat wait between attempts.
- **Observed Behavior**: Preview models (Gemini 3 Flash) are more prone to 503s during peak times.

> ⚠️ Known issue: `ClassifierAgent` occasionally misclassifies "How to use this bot?" as complex due to the presence of session history, even if the history is empty.
