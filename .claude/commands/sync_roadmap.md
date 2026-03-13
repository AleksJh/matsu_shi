Read Roadmap.md and PRD.md in full.

Then scan the project file tree using Glob to inventory what has actually been built.
For each Phase 0–9, check whether the expected directories and files exist.

Update Roadmap.md in-place: prepend ✅ to each phase heading and sub-task line that is
confirmed implemented, 🔄 if partially done, and ⏳ if not started. Do not change any
other text in Roadmap.md.

If the README.md file of the project needs to be updated based on changes then do it also.

Identify the current active step: the first phase that is not fully ✅, and within it,
the first sub-task that is ⏳ or 🔄.

For that step, read all related existing source files, the referenced PRD sections,
and trace the dependency chain (what it imports, what calls it).

Then write ./implement.md with the following sections:
1. Current Phase & Task (phase number, sub-task ID, title)
2. Goal (what this step accomplishes and why it matters)
3. PRD References (exact §sections to re-read before coding)
4. Files to Create (path + one-line description each)
5. Files to Modify (path + what changes)
6. Key Imports & Dependencies (paths of modules this step relies on)
7. Implementation Notes (specific rules, field names, constraints from Roadmap+PRD)
8. Integration Points (how this connects to surrounding phases and components)
9. Done When (the completion criterion for this phase + sub-task verification steps)

Write implement.md in Russian for headings and explanations, English for all code
references, paths, and field names (matching the project language rules).
