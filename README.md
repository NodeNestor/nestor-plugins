# nestor-plugins

Plugin marketplace for Claude Code by [NodeNestor](https://github.com/NodeNestor).

```bash
/plugin marketplace add https://github.com/NodeNestor/nestor-plugins
```

## Plugins

| Plugin | Description |
|--------|-------------|
| [rolling-context](https://github.com/NodeNestor/claude-rolling-context) | Short-term memory. Compresses old messages using Haiku, keeps recent ones verbatim. Zero config, zero latency. |
| [claude-knowledge-graph](https://github.com/NodeNestor/claude-knowledge-graph) | Long-term memory. Knowledge graph with entities, relationships, semantic search, and auto-extraction. |
| [claude-autoresearch](https://github.com/NodeNestor/claude-autoresearch) | Autonomous iterative improvement with fitness functions and keep/revert loop. |
| [claude-autofix](https://github.com/NodeNestor/claude-autofix) | Auto-test and lint after every edit, feeds errors back for self-correction. |
| [claude-guardian](https://github.com/NodeNestor/claude-guardian) | Self-learning convention enforcer. Watches patterns, auto-generates rules. |
| [claude-workflows](https://github.com/NodeNestor/claude-workflows) | Declarative YAML workflow engine. GitHub Actions for Claude Code. |
| [claude-worktrees](https://github.com/NodeNestor/claude-worktrees) | Parallel experiment orchestrator with isolated git worktrees. |

Install any plugin:
```bash
/plugin install <plugin-name>
```
