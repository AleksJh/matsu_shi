Read ./implement.md in full. This file is the authoritative context and action plan for the current development phase.

Then read every file referenced in section "Ссылки на PRD" — load the exact §sections from PRD.md and Roadmap.md that are listed there.

Then read every file listed in section "Файлы для изменения" so you understand existing code before touching it.

Now execute the implementation:

1. Use TodoWrite to create a todo item for each file listed in "Файлы для создания" and each change in "Файлы для изменения". Mark each item in_progress before you start it, completed immediately after.

2. Create every file from "Файлы для создания" with complete, correct content. Follow all rules from "Детали реализации" and "Ключевые импорты и зависимости" precisely — use the exact field names, types, defaults, and code snippets specified there.

3. Apply all changes described in "Файлы для изменения".

4. Respect integration constraints from "Точки интеграции": do not break the contracts that downstream phases depend on.

5. For each feature, search the internet for reputable, out-of-the-box libraries that solve all or part of the task, so we don't end up writing boilerplate code when a ready-made solution exists. If you find any, show them to me and explain their pros and cons. Please estimate what percentage of our requirements they meet and help me make the right call: building from scratch vs. using a library.

Project-wide conventions to follow throughout:
- All user-visible strings (bot messages, UI labels, error messages shown to mechanics) must be in Russian.
- English only for code identifiers, file paths, field names, env var names, and technical references.
- No raw SQL — use SQLAlchemy ORM everywhere except inside Alembic migration files.
- No secrets or credentials in source code — all configuration comes from env vars via pydantic-settings.

After all files are created and modified, go through the checklist in "Критерии завершения" and report the status of each item: which can be verified statically right now, and which require running the stack.

If the README.md file of the project needs to be updated based on changes then do it also.