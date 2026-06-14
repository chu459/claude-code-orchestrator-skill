# Changelog

This page tracks the public docs-facing history of Claude Code Orchestrator Skill.

## v0.6.3 - Docs deploy stability

- Fixed the GitHub Actions docs deploy secret-scan false positive caused by a selftest placeholder token.
- Kept placeholder-secret regression coverage while splitting the sample token string so repository scans do not flag it as a real key.
- Synced README, docs changelog, package metadata, and version metadata for the hotfix.

## v0.6.2 - Actual model attribution

- Fixed #15 by recording Claude stream `modelUsage` as `actual_model_usage`.
- Added `actual_model`, `actual_cost_usd`, `actual_total_tokens`, and `route_mismatch` to run status and metadata.
- `detect_failure_modes` now flags route mismatches as high-severity controller risks.
- `usage-summary`, dashboard, and controller reports now distinguish declared route from actual billed model.
- Added `supervise-decision` as a compatibility alias for `decision-review`.

## v0.6.1 - Issue audit completion

- Expanded `controller-report` / `pressure-report` Markdown with by-model usage totals, total duration, token estimates, output bytes, event bytes, budget stops, warning counts, blocking counts, and max severity.
- Added richer per-run report rows: duration, token estimate, stdout/events bytes, warning/blocking counts, budget state, and source/artifact counts.
- Added token estimates to the dashboard output-budget panel.
- Added warning/blocking risk counts to `usage-summary` and its by-model breakdown.
- Routed remaining legacy metadata writes through the shared UTF-8/control-character sanitizer.

## v0.6.0 - Controller operations hardening

- Fixed GitHub issues #3-#12.
- Added transactional `spawn-role-team` capacity checks and rollback for partial launches.
- Added hard output/event budgets, final-only mode, and output-budget stop reasons for streaming workers.
- `send-instruction` now preserves the prior profile/model by default and reports route drift.
- Added UTF-8 JSON/control-character safeguards for Chinese paths, prompts, metadata, and dashboard output.
- Split risk semantics into blocking state, warnings, max severity, and compatibility `ok`.
- Classified secret scan findings without printing raw secret values.
- Split project source changes from `.agent-workspace` agent artifacts.
- Upgraded the dashboard into a controller operations panel.
- Added `controller-report` / `pressure-report` plus MCP report tools.
- Added supervisor-style `decision-review` / `cc_decision_review`.

## v0.5.1 - Portable assets and safer cleanup

- Fixed GitHub issues #1 and #2.
- Portable `tools/cc-orchestrator` copies now discover `version.json` and Prompt Pack assets.
- `CC_ORCHESTRATOR_SKILL_ROOT` is now honored when users want to point the tool at a full Skill package.
- `healthcheck` now reports `skill_root`, `version_path`, `prompt_pack_path`, and Prompt Pack availability.
- `clean-workspace` now preserves freshly initialized scaffold folders instead of suggesting that they be deleted.
- Selftest now covers Prompt Pack availability and scaffold-preserving cleanup.

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
