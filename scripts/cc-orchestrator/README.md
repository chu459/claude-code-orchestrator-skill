# Claude Code Orchestrator MCP

Local MCP server that lets Codex control Claude Code through CCSwitch profiles.

The server discovers CCSwitch from environment variables and the current user home, reads the CCSwitch database as a model/profile registry, chooses a profile/model from configurable routing rules, injects the selected provider environment into a single `claude` subprocess, and stores runtime artifacts under `.agent-workspace/claude-code-orchestrator/`.

## Tools

- `cc_healthcheck` checks `claude.exe`, CCSwitch files, Python imports, and config.
- `cc_list_profiles` lists Claude profiles from CCSwitch with secrets redacted.
- `cc_pick_profile` explains which profile would be selected for a role/task.
- `cc_run_agent` runs Claude Code once with a selected role/profile and records logs.
- `cc_run_streaming_agent` starts Claude Code as a background worker with `stream-json` events.
- `cc_poll_run` polls compact controller progress by default; raw stdout/stderr/event deltas remain available with raw mode.
- `cc_summarize_run` writes controller artifacts such as progress summary, risk flags, changed files, and timeline.
- `cc_compact_events` compacts raw `events.ndjson` into a small timeline for Codex.
- `cc_stop_run` terminates a specific run id.
- `cc_run_status` lists active streaming workers or inspects one run.
- `cc_send_instruction` stops and restarts a run with recovered context and a new instruction.
- `cc_spawn_role_team` starts multiple role workers and writes a team manifest.
- `cc_collect_team_results` summarizes team output, repeated agreements, and conflicts/risks.
- `cc_cross_review` launches second-round reviewer workers over previous outputs.
- `cc_preflight_write_scope` writes allowed/denied path rules before write-enabled work.
- `cc_check_write_scope` blocks acceptance when a run changed files outside the preflight scope.
- `cc_diff_summary` summarizes changed files, line counts, risk markers, and test need.
- `cc_secret_scan_run` scans run output/events/diff for leaked credentials.
- `cc_rollback_run` conservatively rolls back only when a clean git snapshot proves it is safe.
- `cc_verify_run` runs diff summary, write-scope check, secret scan, optional tests, and a report.
- `cc_benchmark_model` plans or runs a small real benchmark task.
- `cc_benchmark_suite` plans or runs fixed code/review/security/context/multimodal benchmarks.
- `cc_model_registry` builds the local model capability database.
- `cc_calibrate_policy` records local model preference notes.
- `cc_local_policy` reads or writes user-owned model routing overrides that upgrades preserve.
- `cc_score_worker` grades one worker run and records model quality history.
- `cc_prompt_pack` lists or renders reusable worker prompt templates.
- `cc_cost_guard` configures max concurrency and timeout guardrails.
- `cc_usage_summary` estimates daily tokens, duration, failure rate, and model usage from logs.
- `cc_queue_submit`, `cc_queue_tick`, `cc_queue_status`, `cc_queue_cancel`, and `cc_queue_policy` provide priority queue scheduling.
- `cc_upgrade_check` records version state while preserving local calibration, overrides, model registry, quality history, queue policy, and cost settings.
- `cc_mock_stream_test` validates streaming/poll/stop/status with a fake Claude stream.
- `cc_init_workspace` initializes `.agent-workspace`, templates, policy files, rollback/log dirs, and optional `CLAUDE.md`.
- `cc_workspace_status` shows where Codex and Claude Code artifacts will be written.
- `cc_migrate_data` previews or moves legacy `runs`, `reports`, and `dashboard` into the managed workspace.
- `cc_clean_workspace` cleans tmp files, non-scaffold empty dirs, and expired run folders; dry-run by default.
- `cc_archive_runs` zips selected or old run folders under `archives/`.
- `cc_repair_mcp_paths` repairs `.mcp.json` workspace/artifact env values.
- `cc_folder_policy` returns or writes the rule that only agent-generated artifacts are managed.
- `cc_dashboard` generates a local HTML worker dashboard.
- `cc_open_run_folder` opens or returns a run log directory.
- `cc_export_report` writes a Markdown report for a run or team.
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
- Streaming runs write `events.ndjson` in real time from Claude Code `--output-format stream-json --verbose --include-partial-messages`.
- If a run times out, the orchestrator stores any partial stdout/stderr that Python exposes in `.agent-workspace/claude-code-orchestrator/runs/<run_id>/stdout.txt` and `stderr.txt`.
- Use `stop-run` / `cc_stop_run` for runaway workers. It requires an explicit run id.
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
python tools\cc-orchestrator\cc_orchestrator.py init-workspace --cwd .
python tools\cc-orchestrator\cc_orchestrator.py workspace-status --cwd .
python tools\cc-orchestrator\cc_orchestrator.py migrate-data --cwd .
python tools\cc-orchestrator\cc_orchestrator.py clean-workspace --cwd .
python tools\cc-orchestrator\cc_orchestrator.py archive-runs --cwd . --older-than-days 30
python tools\cc-orchestrator\cc_orchestrator.py repair-mcp-paths --cwd . --create
python tools\cc-orchestrator\cc_orchestrator.py folder-policy --cwd . --apply
python tools\cc-orchestrator\cc_orchestrator.py write-claude-md --cwd . --role implementation
python tools\cc-orchestrator\cc_orchestrator.py pick --role implementation --task-type complex_code
python tools\cc-orchestrator\cc_orchestrator.py workflow-plan "Fix the bug"
python tools\cc-orchestrator\cc_orchestrator.py run-streaming "Review this project" --role review
python tools\cc-orchestrator\cc_orchestrator.py run-status
python tools\cc-orchestrator\cc_orchestrator.py poll-run --run-id RUN_ID
python tools\cc-orchestrator\cc_orchestrator.py summarize-run --run-id RUN_ID
python tools\cc-orchestrator\cc_orchestrator.py compact-events --run-id RUN_ID
python tools\cc-orchestrator\cc_orchestrator.py stop-run --run-id RUN_ID --force
python tools\cc-orchestrator\cc_orchestrator.py spawn-role-team "Audit this project" --roles requirements,architecture,security,testing
python tools\cc-orchestrator\cc_orchestrator.py collect-team-results --team-id TEAM_ID
python tools\cc-orchestrator\cc_orchestrator.py mock-stream-test
python tools\cc-orchestrator\cc_orchestrator.py check-write-scope --cwd .
python tools\cc-orchestrator\cc_orchestrator.py verify-run --run-id RUN_ID --test-command "pytest"
python tools\cc-orchestrator\cc_orchestrator.py diff-summary --cwd .
python tools\cc-orchestrator\cc_orchestrator.py secret-scan-run --run-id RUN_ID
python tools\cc-orchestrator\cc_orchestrator.py benchmark-suite
python tools\cc-orchestrator\cc_orchestrator.py usage-summary --write-report
python tools\cc-orchestrator\cc_orchestrator.py queue-submit "Review this project" --role review --priority 100
python tools\cc-orchestrator\cc_orchestrator.py queue-tick --max-concurrent 3
python tools\cc-orchestrator\cc_orchestrator.py queue-policy --max-concurrent 3 --apply
python tools\cc-orchestrator\cc_orchestrator.py model-registry --refresh --apply
python tools\cc-orchestrator\cc_orchestrator.py prompt-pack --list
python tools\cc-orchestrator\cc_orchestrator.py upgrade-check --apply
python tools\cc-orchestrator\cc_orchestrator.py dashboard
python tools\cc-orchestrator\cc_orchestrator.py run-visible "Inspect this project" --role architecture
```

## Configuration

- `config/model_policy.json` controls aliases, task routes, role defaults, timeout limits, and write defaults. The default policy uses `auto:*` aliases so each machine routes to models present in its own CCSwitch database.
- `config/agents.json` controls role prompts.
- CCSwitch remains the source of provider URLs, tokens, and model names.

To add a stronger model later, add or update the provider in CCSwitch, then rerun `score-models`, `write-auto-policy`, and `write-reports`.
