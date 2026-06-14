# Changelog

This page tracks the public docs-facing history of Claude Code Orchestrator Skill.

## v0.5.0 - Workspace governance

- Added `.agent-workspace/claude-code-orchestrator` as the default home for agent-generated artifacts.
- Added `init-workspace`, `workspace-status`, `migrate-data`, `clean-workspace`, `archive-runs`, `repair-mcp-paths`, and `folder-policy`.
- Added matching MCP tools for every workspace governance command.
- Updated worker prompts and generated `CLAUDE.md` so logs, reports, temp files, and rollback notes stay under the managed artifact root.
- Updated install examples and docs so artifact routing works across machines.

## v0.4.1 - Controller checkpoints and queue polish

- Added rolling `checkpoint-###.md` summaries for long-running workers.
- Added deduplicated tool-call summaries, such as `Grep x7` and `Read x3`.
- Made controller-mode `poll-run` write compact controller artifacts by default.
- Added `queued`, `running`, `done`, `failed`, `timed_out`, and `cancelled` queue states.
- Improved the local dashboard layout for model routing, timeline, logs, diff, risk, and controls.

## v0.4.0 - Codex controller system

- Added `references/codex-controller-playbook.md`.
- Added Prompt Pack templates for repo audit, bugfix, security audit, frontend polish, test generation, refactor planning, and release checks.
- Added compact run polling, `cc_summarize_run`, and `cc_compact_events`.
- Added real queue policy, model registry, benchmark history, local override preservation, worker quality history, and failure-mode detection.
- Added timeline dashboard and daily update-check guidance.

## v0.3.0 - Verification and safer operations

- Added one-click `cc_verify_run`.
- Chained diff summary, write-scope checks, secret scanning, optional tests, and Markdown reports.
- Added mock streaming tests that do not spend model quota.
- Added usage summaries, upgrade checks, benchmark suite, and MCP auto-registration.
- Added `version.json` as the version metadata source.

## v0.2.0 - Live worker control

- Added `run-streaming` / `cc_run_streaming_agent`.
- Started Claude Code with `--output-format stream-json --include-partial-messages`.
- Added `poll-run`, `run-status`, and `stop-run`.
- Added role team spawning, result collection, cross review, dashboard, report export, cost guard, and visible worker windows.

## v0.1.0 - Skill, MCP, CLI, and CCSwitch foundation

- Created the Codex Skill entrypoint.
- Added the bundled MCP server and CLI orchestrator.
- Added CCSwitch profile discovery and Claude Code binary discovery.
- Added local model scoring by role and role-based model routing.
- Added safe defaults, run metadata, logs, `CLAUDE.md` generation, UTF-8 output handling, and secret redaction.
