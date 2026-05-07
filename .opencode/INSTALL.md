# Superpowers Installation for OpenCode

## Installation

Add the following to your `opencode.json` (global or project level):

```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]
}
```

After restarting OpenCode, the plugin will automatically install and register all skills.

## Version Pinning

To pin a specific version, specify a tag or branch:

```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git#v1.0.0"]
}
```

## Updates

Superpowers automatically updates on every OpenCode restart by reinstalling the plugin from the Git repository.

## Skill Priority

OpenCode supports skill priorities:
- Project skills have highest priority
- Personal skills come next
- Superpowers skills have lowest priority
