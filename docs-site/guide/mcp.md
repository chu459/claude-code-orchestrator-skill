# MCP setup

MCP is the tool layer. It lets Codex call the orchestrator without copying shell commands by hand.

## Codex config

Add this to Codex `config.toml`:

```toml
[mcp_servers.claude-code-orchestrator]
command = "python"
args = [
  "-c",
  "import os,sys,runpy; home=os.environ.get('CODEX_HOME') or os.path.join(os.environ.get('USERPROFILE') or os.path.expanduser('~'), '.codex'); root=os.environ.get('CC_ORCHESTRATOR_HOME') or os.path.join(home, 'skills', 'claude-code-orchestrator', 'scripts', 'cc-orchestrator'); sys.path.insert(0, root); runpy.run_path(os.path.join(root, 'server.py'), run_name='__main__')"
]

[mcp_servers.claude-code-orchestrator.env]
PYTHONIOENCODING = "utf-8"
PYTHONUTF8 = "1"
```

The same example lives in:

```text
docs/mcp.codex.example.toml
```

## Tools

| Tool | What it does |
| --- | --- |
| `cc_healthcheck` | Checks Claude Code, CCSwitch, Python, and config |
| `cc_list_profiles` | Lists CCSwitch profiles with secrets redacted |
| `cc_pick_profile` | Shows which profile and model a role would use |
| `cc_run_agent` | Runs one Claude Code worker |
| `cc_run_visible_agent` | Opens a visible Claude Code worker window |
| `cc_last_run` | Reads the latest run metadata and output tails |
| `cc_git_diff` | Returns a capped git diff for review |
| `cc_workflow_plan` | Builds the configured multi-agent workflow plan |
| `cc_write_claude_md` | Writes project instructions for Claude Code workers |
| `cc_score_models` | Scores models discovered from CCSwitch |
| `cc_write_strategy_reports` | Writes model score and strategy reports |

## Safe defaults

By default, worker runs use plan mode.

Pass `allow_write=true` only after Codex has decided that file edits are needed and the write scope is clear.

Secrets are redacted from tool output and persisted logs, but prompts should still avoid asking for raw secrets.

## Smoke test

After restarting Codex, call:

```text
cc_healthcheck
cc_list_profiles
cc_score_models
```

If these work, Codex can route workers through MCP.
