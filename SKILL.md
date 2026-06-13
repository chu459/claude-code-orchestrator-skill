---
name: claude-code-orchestrator
description: Control Claude Code as an external sub-agent through the local cc-orchestrator MCP/CLI and CCSwitch profiles. Use when the user asks Codex to use Claude Code, CCSwitch, external model routing, visible Claude Code windows, ClaudeCode as subagents, MCP control of Claude Code, or a configurable multi-agent workflow where Codex is the controller and Claude Code agents are workers.
---

# Claude Code Orchestrator

Use this skill when Codex should control Claude Code through the bundled orchestrator. Prefer `$env:CC_ORCHESTRATOR_HOME` when set; otherwise use the installed skill's `scripts/cc-orchestrator` directory or the current workspace's `tools/cc-orchestrator`.

## Operating Model

Codex remains the controller. Claude Code is an external worker launched through the orchestrator. Do not treat Claude Code output as final until Codex has reviewed logs, diffs, and verification results.

Default routing:

- Discover CCSwitch from `$env:CCSWITCH_HOME`, `$env:USERPROFILE\.cc-switch`, or the current user home.
- Discover Claude Code from `$env:CLAUDE_CODE_BIN`, `where claude`, and common Claude Code install paths.
- Score every Claude model found in CCSwitch, then choose the best local model for each agent role.

The orchestrator reads CCSwitch profiles in read-only mode and injects provider env vars only into the launched Claude Code process. It should not rewrite CCSwitch global state.

## Preferred Commands

If `$env:CC_ORCHESTRATOR_HOME` is not set, set it to the workspace orchestrator path first:

```powershell
$workspaceTool = Join-Path (Get-Location) "tools\cc-orchestrator"
$installedSkillTool = Join-Path $env:USERPROFILE ".codex\skills\claude-code-orchestrator\scripts\cc-orchestrator"
$env:CC_ORCHESTRATOR_HOME = if (Test-Path $workspaceTool) { $workspaceTool } else { $installedSkillTool }
```

Healthcheck:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" healthcheck
```

Fast self-test for UTF-8 handling and required config files:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" selftest
```

List profiles:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" list-profiles
```

Score local models:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" score-models
```

Write the portable auto-routing policy:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" write-auto-policy
```

Generate score and strategy reports:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" write-reports
```

Pick a route without running Claude Code:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" pick --role implementation --task-type complex_code
```

Run Claude Code non-interactively:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run "TASK" --role architecture
```

For long multi-agent work, split prompts into short role-specific tasks and set a clear timeout. If a run times out, inspect the saved run folder instead of rerunning blindly:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" last-run
```

Open a visible Claude Code window:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run-visible "TASK" --role architecture
```

Inspect last run:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" last-run
```

Inspect diff after write-enabled work:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" diff --cwd "PROJECT_PATH"
```

## Safety Rules

- Default to read-only/plan mode.
- Use `--allow-write` only for scoped implementation tasks after Codex has identified the write set.
- Never print or persist raw API keys. The orchestrator redacts secrets, but still avoid requesting secrets in prompts.
- After any write-enabled Claude Code run, inspect diffs and run verification before reporting success.
- If the user wants to watch Claude Code work, use `run-visible`.
- Windows Chinese output is handled with UTF-8 stdio and child-process UTF-8 env. If a host still renders text strangely, rely on the UTF-8 files under `runs/<run_id>/`.
- Timeout output is preserved when the subprocess exposes partial stdout/stderr; use `last-run` to recover the tails.

## Four-Phase Workflow

For the user's multi-agent workflow:

1. Run or plan requirements, architecture, security, and testing roles.
2. Cross-review architecture with security/testing feedback.
3. Use implementation only after the plan is stable; keep writes scoped.
4. Summarize role conclusions, conflicts, final changes, verification, and deployment advice.

Use:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" workflow-plan "TASK"
```

before launching a full workflow.

