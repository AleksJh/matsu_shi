---
type: procedural
zone: procedures
last_updated: 2026-05-07
source_files:
  - backend/scripts/ingest.py
  - ingest_wiki.md
related:
  - "[[database]]"
  - "[[rag-pipeline]]"
  - "[[integrations]]"
---

# PDF Ingestion Procedure

The ingestion pipeline is a critical workflow that converts raw technical manuals into a searchable, vector-indexed knowledge base. 

## Workflow Overview

Due to the heavy use of external APIs (Gemini, OpenRouter) and the need for local PDF access, the ingestion script is designed to run **locally on a developer machine**, writing results to the production VPS via a secure tunnel.

### Step 1: Open SSH Tunnel
Before starting, create a tunnel to the production database:
```bash
ssh -L 5432:localhost:5432 user@your-vps-ip -N
```
*Keep this terminal window open during the entire process.*

### Step 2: Run Ingest Script
Execute the script from the `backend/` directory:
```bash
DATABASE_URL="postgresql+asyncpg://postgres:PASSWORD@localhost:5432/matsu_shi" \
PYTHONPATH=. \
uv run python scripts/ingest.py \
  --path "/path/to/manual.pdf" \
  --machine-model "PC300-8" \
  --category "maintenance" \
  --save-artifacts \
  --dry-run
```

### Key CLI Flags
- `--path PATH`: Path to a single PDF manual.
- `--dir DIR`: Batch mode; processes all PDFs in the directory.
- `--machine-model MODEL`: Mandatory identifier (e.g., "PC300-8").
- `--dry-run`: Parses and chunks the document without writing to the database or R2.
- `--artifact-dir DIR`: Custom directory for step artifacts (default: `./cache`).
- `--save-artifacts`: Enables full checkpointing (required for production).

## The 6-Step Pipeline

1.  **Parse (Docling)**: Extracts text, tables, and image positions into structured Markdown.
2.  **Visual (Gemini Vision)**: Renders diagram pages at 150 DPI, uploads to Cloudflare R2, and generates technical descriptions.
3.  **Chunk (Rules-based)**: Splits Markdown by headers (H1-H4), isolates tables, and applies 10% token overlap.
4.  **Enrich (Gemini Lite)**: Writes a one-sentence technical summary for each chunk and prepends it as `[Контекст: ...]`.
5.  **Embed (OpenRouter)**: Generates 1024-dimensional vectors using `qwen3-embedding-4b`.
6.  **Write**: Inserts metadata and vectors into PostgreSQL and updates document status to `indexed`.

## Processing Optimizations

### Large PDF Handling (60-page Chunks)
To prevent `std::bad_alloc` errors and heap corruption in `pypdfium2`, the script splits large PDFs into temporary 60-page documents. Each chunk is processed in a fresh document context, ensuring stability even for 1000+ page manuals.

### Post-processing Rules
- **Small Chunk Merging**: Any text chunk containing fewer than `CHUNK_MIN_TOKENS` (80) is automatically merged into the preceding text chunk to maintain high retrieval quality.
- **Checksum Deduplication**: Before starting the pipeline, the script computes a SHA256 checksum of the PDF. If a document with the same checksum already exists in the database, the ingestion is skipped unless `--rebuild-index` is used.
- **Partial Progress Saving**: For the `Visual` and `Enrich` stages, progress is saved to `*_partial.json` after every item. This allows resuming from the exact point of failure within a stage.

## Checkpoints & Resuming

Ingestion can take 20-60 minutes for large manuals. The system includes a checkpointing mechanism to avoid data loss.

| Flag | Purpose |
| :--- | :--- |
| `--save-artifacts` | Saves result of each step to `cache/{sha256}/`. |
| `--stop-after STEP` | Stops the pipeline after a specific step for inspection. |
| `--start-from STEP` | Resumes from a specific step using cached JSON files. |
| `--rebuild-index` | Deletes existing chunks for the document before re-indexing. |

### Resume Example:
If the process fails during the `embed` step (e.g., API timeout):
```bash
python scripts/ingest.py --path manual.pdf --machine-model "PC300-8" --start-from embed
```

## Naming Conventions
- **Machine Model**: Use the base model name (e.g., `PC300-8`) for all variants (EO, -8LC). This ensures the RAG pipeline can find the manual regardless of minor market suffixes.
- **Category**: Use `maintenance` for Service Manuals (SM) and `operations` for Operations Manuals (OM).

> ⚠️ Warning: Never run the ingestion script without `--save-artifacts` for production documents, as transient API failures could waste significant time and cost.
