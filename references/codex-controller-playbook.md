# Codex Controller Playbook

Codex is the controller. Claude Code workers are hands. A worker result is input, not the final answer.

## 1. Decide Who Should Work

Do it inside Codex when:

- The task is small enough to finish directly.
- The user asks for a final answer, short edit, or simple command.
- The answer needs judgment more than exploration.
- The change touches sensitive files and no write scope is set.

Send Claude Code when:

- The task benefits from parallel reading, repo audit, tests, or second opinions.
- The user asks for multi-agent work.
- The work is large enough that separate roles help: requirements, development, security, testing, review, documentation, automation.
- Codex needs a cheaper worker model while keeping the best model as the brain.

Use visible Claude Code only when the user wants to watch or manually steer it.

## 2. Default Run Pattern

1. Codex reads enough local context to define the task.
2. Codex writes or checks the allowed write scope.
3. Codex picks one worker role and one prompt template.
4. Codex starts the worker with `cc_run_streaming_agent`.
5. Codex polls with `cc_poll_run --mode controller`.
6. Codex stops, reviews, verifies, or cross-reviews based on signals.
7. Codex gives the final answer only after verification.

For multi-agent work, prefer queue submission over launching every worker at once.

## 3. Poll Cadence

Use this cadence unless the user asks otherwise:

- First poll: 10 to 20 seconds after start.
- Normal poll: every 30 to 60 seconds.
- High-risk write run: every 15 to 30 seconds.
- Long read-only audit: every 60 to 120 seconds.
- If the worker reports a decision, edit, test, error, or risk, poll again sooner.

Codex should normally read controller artifacts, not raw logs:

- `progress_summary.json`
- `latest_decision.md`
- `risk_flags.json`
- `changed_files.json`
- `tool_timeline.md`

Read raw `events.ndjson` only when debugging or when the compact summary is unclear.

## 4. Stop Signals

Stop or downgrade the worker when any of these appear:

- It edits outside the write scope.
- It starts touching unrelated files.
- It leaks or prints possible secrets.
- It repeats the same search or command without new findings.
- It produces a lot of output but no decisions.
- It claims success while tests failed.
- It is active but no meaningful event appears for too long.
- It ignores the assigned role.
- It plans destructive actions without explicit permission.

Use `cc_stop_run` first. Use force only when the process does not exit.

## 5. Cross-Review Rules

Use `cc_cross_review` when:

- A worker changed security, auth, install, release, data, or file deletion behavior.
- Two workers disagree.
- The diff is large or hard to reason about.
- The worker solved the issue but tests are weak.
- The user asked for high confidence.

Recommended reviewer pairs:

- Development output -> review + testing.
- Architecture output -> security + compatibility.
- Security output -> review + testing.
- Documentation output -> compatibility + requirements.

## 6. When Writes Are Allowed

Allow writes only when all are true:

- The user asked for implementation or clearly expects a change.
- Codex has set a write scope.
- The task prompt says exactly what may change.
- The worker role is development, documentation, automation, or another write-approved role.
- There is a rollback path through git diff or a clean snapshot.

Never let a worker write secrets, dependency credentials, personal data, or global machine config unless the user explicitly asks.

## 7. Verification Gate

After every write-enabled run, call `cc_verify_run`.

The verify gate includes:

- `cc_diff_summary`
- `cc_secret_scan_run`
- `cc_check_write_scope`
- optional test commands
- Markdown report
- worker quality score

Do not report success if any gate blocks acceptance. Say what failed and what was done next.

## 8. Queue Policy

Use the queue when more than one worker may run.

Default policy:

- `max_concurrent`: 3
- higher `priority` runs first
- retry failed read-only jobs once
- do not retry write-enabled jobs automatically
- stop timed-out jobs
- keep `queued`, `running`, `succeeded`, `failed`, `cancelled`, and `timed_out` states

Raise concurrency only when the user accepts the cost.

## 9. Model Routing

Use real local history when available:

1. `local_policy.override.json`
2. `model_registry.json`
3. `model_benchmark_history.json`
4. current CCSwitch profile scan
5. fallback heuristic score

Local override is user-owned. Upgrades must preserve it.

## 10. Final Controller Checklist

Before final answer:

- Did Codex inspect the latest run summary?
- Did Codex inspect the diff?
- Did `cc_verify_run` pass if anything was written?
- Did secret scan pass?
- Did write scope pass?
- Did tests run or was the lack of tests explained?
- Was any cross-review needed?
- Is the final answer based on Codex judgment, not worker text copied blindly?
