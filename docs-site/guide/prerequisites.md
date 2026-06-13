# Prerequisites

You need five things before this Skill is useful.

## Codex

Codex is the controller.

It plans the work, calls MCP tools, launches workers, reviews logs, checks diffs, and gives the final answer.

## Claude Code

Claude Code is the worker process.

The orchestrator launches `claude` with a selected role, prompt, permission mode, and provider environment.

Check that the command is available:

```bash
claude --version
```

You can also set a custom binary:

```bash
export CLAUDE_CODE_BIN="/path/to/claude"
```

On Windows:

```powershell
$env:CLAUDE_CODE_BIN = "C:\Path\To\claude.exe"
```

## CCSwitch

CCSwitch is the local profile registry and model router.

The orchestrator reads CCSwitch in read-only mode. It does not rewrite global CCSwitch state. It injects the selected provider variables only into the launched Claude Code process.

Discovery checks:

- `$env:CCSWITCH_HOME`
- `$env:USERPROFILE\.cc-switch`
- the current user home

## Multiple models in CCSwitch

Configure more than one Claude-compatible model inside CCSwitch.

The Skill becomes stronger when each model has a job:

| Model class | Good for |
| --- | --- |
| Strong reasoning model | architecture, review, security |
| Strong code model | implementation and refactoring |
| Fast low-cost model | quick checks and small planning tasks |
| Stable review model | risk, testing, compatibility |
| Fallback model | resilience when a route is missing |

After adding models, rerun:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" score-models
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-auto-policy
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-reports
```

## Python 3.10+

The bundled CLI and MCP server are Python programs.

Check:

```bash
python --version
```

If your system uses `python3`, use that command in the examples.
