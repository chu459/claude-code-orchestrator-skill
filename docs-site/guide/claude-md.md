# CLAUDE.md

Claude Code can read a project-level `CLAUDE.md`.

The orchestrator can write one so each worker knows its role and boundaries before it starts.

## Create one

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-claude-md --cwd /path/to/project --role implementation
```

For review:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-claude-md --cwd /path/to/project --role review
```

Through MCP, Codex can call:

```text
cc_write_claude_md
```

## What it tells the worker

The generated file tells Claude Code:

- Codex is the controller, planner, reviewer, and final decision maker.
- Claude Code is an external worker process.
- The worker has one assigned role.
- Secrets must not be printed.
- Destructive commands are not allowed unless explicitly requested.
- Unrelated user changes must not be reverted.
- Progress and verification should be reported clearly.

## Existing files are protected

If `CLAUDE.md` already exists, the command is conservative.

| Option | Behavior |
| --- | --- |
| default | Refuses to overwrite an existing unmanaged file |
| `--append` | Adds the managed orchestrator section |
| `--force` | Writes a timestamped backup, then replaces the file |

## Recommended flow

1. Codex plans the work.
2. Codex writes `CLAUDE.md` for the selected role.
3. Codex launches Claude Code through CLI or MCP.
4. Claude Code follows the role rules.
5. Codex reviews logs, diffs, and verification results.
