---
name: claude-code-orchestrator
description: Control Claude Code as an external sub-agent through the local cc-orchestrator MCP/CLI and CCSwitch profiles. Use when the user asks Codex to use Claude Code, CCSwitch, external model routing, visible Claude Code windows, ClaudeCode as subagents, MCP control of Claude Code, or a configurable multi-agent workflow where Codex is the controller and Claude Code agents are workers.
---

# Claude Code Orchestrator

Use this skill when Codex should control Claude Code through the bundled orchestrator. Prefer `$env:CC_ORCHESTRATOR_HOME` when set; otherwise use the installed skill's `scripts/cc-orchestrator` directory or the current workspace's `tools/cc-orchestrator`.

## Operating Model

Codex remains the controller. Claude Code is an external worker launched through the orchestrator. Do not treat Claude Code output as final until Codex has reviewed logs, diffs, and verification results.

Codex owns planning, write-scope decisions, final review, and final response. Claude Code agents only provide role-specific analysis or scoped edits when Codex explicitly enables write access.

Default routing:

- Discover CCSwitch from `$env:CCSWITCH_HOME`, `$env:USERPROFILE\.cc-switch`, or the current user home.
- Discover Claude Code from `$env:CLAUDE_CODE_BIN`, `where claude`, and common Claude Code install paths.
- Score every Claude model found in CCSwitch, then choose the best local model for each agent role.

The orchestrator reads CCSwitch profiles in read-only mode and injects provider env vars only into the launched Claude Code process. It should not rewrite CCSwitch global state.

## Worker Roles

Supported primary roles:

- `requirements`: clarify needs, gaps, plans, constraints, and acceptance criteria.
- `development`: implement scoped code changes when write access is granted.
- `testing`: design or run focused checks, edge cases, and failure-mode tests.
- `review`: review code quality, bugs, maintainability, and release blockers.
- `performance`: inspect slow paths, resource use, blocking IO, and measurable optimizations.
- `compatibility`: check OS, shell, dependency, version, and install portability.
- `documentation`: improve examples, onboarding, FAQ, and troubleshooting.
- `automation`: design CI/CD, tests, packaging, release, and repeatable scripts.
- `security`: audit secrets, permissions, injection, privacy, and destructive paths.
- `ops`: check deployment, logs, observability, release safety, and rollback.

Legacy/support roles still work: `architecture`, `implementation`, and `multimodal`.

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

Create or update a project `CLAUDE.md` for Claude Code sub-agents:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" write-claude-md --cwd "PROJECT_PATH" --role development
```

If a project already has `CLAUDE.md`, preserve it by default. Use `--append` to add the managed orchestrator section, or `--force` to replace after writing a timestamped backup.

Pick a route without running Claude Code:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" pick --role performance --task-type performance_review
```

Run Claude Code non-interactively:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run "TASK" --role development
```

For long multi-agent work, split prompts into short role-specific tasks and set a clear timeout. If a run times out, inspect the saved run folder instead of rerunning blindly:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" last-run
```

Open a visible Claude Code window:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run-visible "TASK" --role review
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
- When Claude Code needs a stable persona, project rules, or role-specific worker behavior, write `CLAUDE.md` first with `write-claude-md` or MCP tool `cc_write_claude_md`, then run the sub-agent from that project cwd.

## Four-Phase Workflow

For the user's multi-agent workflow:

1. Codex plans the write scope and asks role workers for focused input.
2. Run or plan requirements, development, testing, review, performance, compatibility, documentation, automation, security, and ops roles as needed.
3. Cross-review conflicts before enabling any scoped write role.
4. Codex reviews logs, diffs, and verification, then gives the final answer.

Use:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" workflow-plan "TASK"
```

before launching a full workflow.

## MCP Parameter Notes

Use the same role names through MCP:

- `cc_pick_profile`, `cc_run_agent`, `cc_run_visible_agent`, and `cc_write_claude_md` accept `role`.
- `role` supports `requirements`, `development`, `testing`, `review`, `performance`, `compatibility`, `documentation`, `automation`, `security`, `ops`, plus `architecture`, `implementation`, and `multimodal`.
- `task_type` supports `simple`, `normal`, `complex_code`, `development`, `review`, `security_review`, `performance_review`, `compatibility_review`, `documentation`, `automation`, `architecture`, `multimodal`, and `ops`.
- `cc_workflow_plan` returns `controller: codex`, `worker_roles`, and one route per configured role.
- `cc_score_models` returns `role_scores` for all configured roles.
- `cc_write_claude_md` embeds the selected role prompt and states that Codex is the controller.

