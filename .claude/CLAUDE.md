Wiki Usage
Before starting any dev work, run `/wiki-prime`. It reads `wiki/index.md` (system overview + page catalog) and the relevant zone page for the current task. This is the primary source of project context.
When working on a specific component, read its wiki page if it exists (e.g. `wiki/backend/rag-pipeline.md` before touching RAG code).
**Raw Dumps**: At the end of a logical task or session, run `/wiki-raw` and provide a high-quality summary of changes, decisions, and debt. This is the only way the wiki stays alive.
**No Direct Edits**: Do not write to `wiki/` files except `wiki/raw/`. The wiki is maintained by a separate compilation agent (OpenCode) to ensure consistency.

General Principles
Language: Chat in Russian. All technical output (code, comments, commits) must be in English.
Decision Making:
- Critical (Tech stack, architecture, security): STOP and ask me. Provide a summary, options, and pros/cons.
- Minor: Act independently. Provide a summary and justification at the end.

Engineering Standards
- Git: Commit every logical subtask. Clear messages. Analyze history for complex issues.
- TDD: Write robust tests (logic, security) before coding. Run full regression after each session. If you think you should rewrite an existing test to be better - ask my permission and explain me the necessity.
- Security by Design: Apply cybersecurity standards from line one. Validate with specialized tests.
- No Shortcuts: Implement general, robust logic. No hard-coding. No "time constraint" excuses.
- Context Management: Read files before editing. No speculation.

Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.
Before implementing:
State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.

Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

Surgical Changes
Touch only what you must. Clean up only your own mess.
When editing existing code:
Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:
Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

Goal-Driven Execution
Define success criteria. Loop until verified.
Transform tasks into verifiable goals:
"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:
1. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.