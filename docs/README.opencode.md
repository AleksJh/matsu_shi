# OpenCode Integration

## Skill Priority

OpenCode supports skill priorities:
- **Project skills** (`.opencode/skills/`) - highest priority
- **Personal skills** (`~/.opencode/skills/`) - medium priority
- **Superpowers skills** (`skills/`) - lowest priority

## Tool Mapping

| Claude Code | OpenCode |
|-------------|----------|
| TodoWrite | todowrite |
| Task | @mention system |
| Skill | skill |
| Read/Write/Edit/Bash | Native tools |

## Available Skills

Skills are automatically discovered from the `skills/` directory when the superpowers plugin is loaded.
