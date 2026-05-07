---
description: Create a new raw session dump file in wiki/raw/ with correct timestamp naming
---

# /wiki-raw — Save Raw Session Material

Creates a new file in `wiki/raw/` ready for you to paste a session summary into.

## Steps

1. Get the current date and time using PowerShell:
   ```powershell
   Get-Date -Format "yyyy-MM-dd-HH-mm"
   ```

2. Build the filename:
   - If an argument was provided (e.g. `/wiki-raw rag-tuning`): `wiki/raw/YYYY-MM-DD-HH-MM-rag-tuning.md`
   - If no argument: `wiki/raw/YYYY-MM-DD-HH-MM.md`
   - Lowercase, spaces replaced with hyphens

3. Create the file with this template:
   ```markdown
   # Session: <topic or "Untitled">
   Date: YYYY-MM-DD HH:MM
   
   ## Summary
   
   <!-- User pastes session summary or compaction output here -->
   
   ## Key Changes
   
   <!-- What was built, fixed, or decided -->
   
   ## Open Questions / Next Steps
   
   <!-- What remains, blockers, follow-ups -->
   ```

4. Report the full path to the user so they can open it immediately.

Do not open any other files. Do not read the wiki. Just create the file and report its path.

The placeholders are for the human to fill, not you.
