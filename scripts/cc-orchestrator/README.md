# Claude Code Orchestrator MCP

Local MCP server that lets Codex control Claude Code through CCSwitch profiles.

The server discovers CCSwitch from environment variables and the current user home, reads the CCSwitch database as a model/profile registry, chooses a profile/model from configurable routing rules, injects the selected provider environment into a single `claude` subprocess, and stores each run under `runs/`.

## Tools

- `cc_healthcheck` checks `claude.exe`, CCSwitch files, Python imports, and config.
- `cc_list_profiles` lists Claude profiles from CCSwitch with secrets redacted.
- `cc_pick_profile` explains which profile would be selected for a role/task.
- `cc_run_agent` runs Claude Code once with a selected role/profile and records logs.
- `cc_run_visible_agent` opens Claude Code in a visible PowerShell window with the selected profile.
- `cc_last_run` returns the latest run metadata and tail output.
- `cc_git_diff` returns a capped `git diff` for post-run review.
- `cc_workflow_plan` returns the configured four-phase multi-agent role/model plan.
- `cc_write_claude_md` writes a project `CLAUDE.md` persona/instructions file for Claude Code workers.
- `cc_score_models` scores local CCSwitch models with local heuristics.
- `cc_write_strategy_reports` writes model score and routing reports.

Write access is disabled by default in `config/model_policy.json`. A caller must pass `allow_write=true` to `cc_run_agent`; otherwise the orchestrator uses `--permission-mode plan`.

## Reliability notes

- CLI and MCP JSON output force UTF-8 so Chinese text and symbols do not crash Windows GBK consoles.
- Child Claude Code runs receive UTF-8 Python environment variables, and visible PowerShell sessions set UTF-8 input/output encoding.
- If a run times out, the orchestrator stores any partial stdout/stderr that Python exposes in `runs/<run_id>/stdout.txt` and `stderr.txt`.
- For large multi-agent work, prefer several short role-specific prompts over one broad prompt. Then use `last-run` or `cc_last_run` to inspect saved tails before retrying.

## Run

```powershell
python tools\cc-orchestrator\server.py
```

This workspace includes a root `.mcp.json` that starts the server with:

```json
{
  "claude-code-orchestrator": {
    "command": "python",
    "args": ["tools/cc-orchestrator/server.py"]
  }
}
```

For direct smoke tests:

```powershell
python tools\cc-orchestrator\cc_orchestrator.py healthcheck
python tools\cc-orchestrator\cc_orchestrator.py selftest
python tools\cc-orchestrator\cc_orchestrator.py list-profiles
python tools\cc-orchestrator\cc_orchestrator.py score-models
python tools\cc-orchestrator\cc_orchestrator.py write-auto-policy
python tools\cc-orchestrator\cc_orchestrator.py write-reports
python tools\cc-orchestrator\cc_orchestrator.py write-claude-md --cwd . --role implementation
python tools\cc-orchestrator\cc_orchestrator.py pick --role implementation --task-type complex_code
python tools\cc-orchestrator\cc_orchestrator.py workflow-plan "Fix the bug"
python tools\cc-orchestrator\cc_orchestrator.py run-visible "Inspect this project" --role architecture
```

## Configuration

- `config/model_policy.json` controls aliases, task routes, role defaults, timeout limits, and write defaults. The default policy uses `auto:*` aliases so each machine routes to models present in its own CCSwitch database.
- `config/agents.json` controls role prompts.
- CCSwitch remains the source of provider URLs, tokens, and model names.

To add a stronger model later, add or update the provider in CCSwitch, then rerun `score-models`, `write-auto-policy`, and `write-reports`.
