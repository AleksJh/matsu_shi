# Matsu Shi — LLM Wiki

This is a Karpathy-style knowledge base for the Matsu Shi project. It is designed to be read and maintained by LLM agents to provide persistent project context across development sessions.

## Structure

- `index.md`: The main entry point. Contains a **System Overview** and a **Page Catalog**.
- `SCHEMA.md`: Rules and standards for the wiki. Read this if you are a compilation agent.
- `BOOTSTRAP.md`: Instructions for the initial codebase analysis.
- `log.md`: Append-only log of wiki operations (ingest, bootstrap, lint).
- `raw/`: Immutable session dumps. This is where the development agent (`Claude Code`) writes new information.
- `architecture/`, `backend/`, `frontend/`, etc.: Zone directories containing detailed technical pages.

## Workflow

1. **Development**: The agent works on the codebase. At the end of a session, it runs `/wiki-raw` to create the appropriate file where the human user will save a summary of changes and decisions to `wiki/raw/`.
2. **Compilation**: A separate agent (`OpenCode` or other) reads the new files in `raw/`, updates the relevant pages in the zone directories, and logs the operation in `log.md`.
3. **Consumption**: At the start of a new session, the agent runs `/wiki-prime` to load the current system state and relevant component details from the wiki.

## Maintenance

The wiki is maintained by a "Library" agent. Do not edit pages in zone directories manually unless you are fixing formatting or structural issues. All substantive knowledge should flow through the `raw/` directory.

