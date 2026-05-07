# Wiki Schema

Rules for the compilation agent (OpenCode / any LLM agent).
**Read this file first before any wiki operation.**

---

## Role

You maintain this wiki. You read raw session dumps from `raw/` and update pages in zone directories. You never modify `raw/` files. You write everything else.

---

## Frontmatter

Every wiki page starts with YAML frontmatter:

```yaml
---
type: architecture | component | procedure | integration | state
zone: architecture | backend | frontend | infrastructure | integrations | procedures
last_updated: YYYY-MM-DD
source_files:
  - path/to/file.py
related:
  - "[[other-page]]"
---
```

- `source_files`: actual repo paths this page was built from
- `related`: WikiLinks to pages with meaningful connections
- Always update `last_updated` when you modify a page

---

## WikiLinks

Use Obsidian-style links: `[[page-name]]` — filename without `.md`, relative to wiki root.

Examples:
- `[[rag-pipeline]]` → links to `backend/rag-pipeline.md`
- `[[overview]]` → links to `architecture/overview.md`

When you create or update a page, add `[[back-links]]` in the `related` field of the pages you reference.

---

## Zone Map

| Zone | Directory | What belongs there |
|------|-----------|--------------------|
| architecture | `architecture/` | System overview, component map, data flow, key decisions |
| backend | `backend/` | RAG pipeline, agents, API, bot, database, auth, services |
| frontend | `frontend/` | Telegram Mini App, admin dashboard |
| infrastructure | `infrastructure/` | Docker Compose, Nginx, deployment, environment vars |
| integrations | `integrations/` | OpenRouter, Langfuse, Cloudflare R2, Jina, Telegram API |
| evaluation | `evaluation/` | Golden datasets, RAG metrics (relevancy, faithfulness), test results |
| security | `security/` | Threat models, HMAC validation, auth flow audits, PII handling |
| procedures | `procedures/` | Document ingestion workflow, deploy steps, monitoring |

---

## index.md

The primary entry point — two parts in one file:

**Top section (System Overview):** A concise summary of the system: what it is, key architectural decisions, how components connect, current phase, active blockers. Keep this under 60 lines. Update when architecture or phase changes.

**Bottom section (Page Catalog):** One line per wiki page, organized by zone:
```
- [[page-name]] — one-sentence summary
```
Update the catalog on every ingest when pages are created or significantly changed. Keep summaries under 100 chars.

---

## log.md

Append-only operation log. Each entry:

```markdown
## [YYYY-MM-DD] operation | Title

- Files updated: list
- Raw sources consumed: list (filenames only)
- Notes: anything unexpected or worth flagging
```

Operations: `bootstrap`, `ingest`, `query`, `lint`.

Always append — never edit existing entries.

---

## Page Writing Rules

1. **Descriptive, not prescriptive** — document what IS, not what should be. Flag known debt with `> ⚠️ Known issue: ...`
2. **Code paths over prose** — prefer `backend/app/rag/retriever.py:dense_search()` over "the dense search function"
3. **WikiLinks liberally** — every mention of another component should be a `[[link]]`
4. **Contradictions** — if new raw material contradicts an existing page, update the page and note the change in log.md
5. **No speculation** — only what you can verify from source files or raw material

---

## raw/ Rules

- Raw files are immutable — read only, never edit or delete
- One raw file = one session dump or topic summary
- Naming: `YYYY-MM-DD-HH-MM[-topic].md`
- After processing a raw file, note it in log.md under "Raw sources consumed"

---

## Ingest Workflow

When new raw files appear:

1. Read all new `raw/` files (those not yet in log.md)
2. For each raw file, identify which wiki zones/pages are affected
3. Update or create pages in the relevant zones
4. Update cross-references (`related` frontmatter) on touched pages
5. Update `index.md` for any new pages
6. Update `index.md` (System Overview) if architecture or critical patterns changed
7. Append one entry to `log.md`

---

## Lint Checklist

Run periodically to keep the wiki healthy:

- [ ] Pages with no inbound `[[links]]` (orphans)
- [ ] Concepts mentioned but lacking their own page
- [ ] `source_files` pointing to files that no longer exist
- [ ] Sections marked `> ⚠️` that have since been resolved
- [ ] `index.md` System Overview section over 60 lines (trim, move details to zone pages)
- [ ] `index.md` missing recently created pages
- [ ] **Contradictions**: Overview content contradicts specific zone pages (Architecture vs API, etc.)
