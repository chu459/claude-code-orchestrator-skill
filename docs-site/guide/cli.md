# CLI reference

The CLI is `cc_orchestrator.py`.

Set `CC_ORCHESTRATOR_HOME` first:

```bash
export CC_ORCHESTRATOR_HOME="$HOME/.codex/skills/claude-code-orchestrator/scripts/cc-orchestrator"
```

Windows PowerShell:

```powershell
$env:CC_ORCHESTRATOR_HOME = "$env:USERPROFILE\.codex\skills\claude-code-orchestrator\scripts\cc-orchestrator"
```

## Health and discovery

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" selftest
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" healthcheck
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" list-profiles
```

Use these before running workers.

## Routing

Pick a route without launching Claude Code:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" pick --role implementation --task-type complex_code
```

Build a full workflow plan:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" workflow-plan "Refactor this project safely"
```

## Model scoring and reports

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" score-models
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-auto-policy
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-reports
```

`write-auto-policy` updates routing aliases so local models are selected by role.

`write-reports` writes model score and strategy reports under the orchestrator.

## Run workers

Run a read-only architecture worker:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" run "Map this repository architecture" --role architecture
```

Run a scoped write-capable implementation worker:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" run "Fix the failing test in src/foo.py" --role implementation --allow-write --cwd /path/to/project
```

Open a visible Claude Code window:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" run-visible "Inspect this project" --role architecture
```

## Review runs

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" last-run
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" diff --cwd /path/to/project
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" verify-run --run-id <run_id> --test-command "npm test"
```

Runs are stored under:

```text
scripts/cc-orchestrator/runs/<run_id>/
  metadata.json
  prompt.txt
  stdout.txt
  stderr.txt
```

On Windows, tail stdout:

```powershell
Get-Content "$env:CC_ORCHESTRATOR_HOME\runs\<run_id>\stdout.txt" -Wait
```

On macOS or Linux:

```bash
tail -f "$CC_ORCHESTRATOR_HOME/runs/<run_id>/stdout.txt"
```

## Live control

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" run-streaming "Review this repo" --role review
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" poll-run --run-id <run_id>
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" summarize-run --run-id <run_id>
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" compact-events --run-id <run_id>
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" run-status
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" stop-run --run-id <run_id> --force
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" mock-stream-test
```

`poll-run` defaults to controller mode. It returns compact progress, risk flags, changed files, a timeline, deduplicated tool-call summary, and rolling checkpoint paths instead of dumping raw events.

`mock-stream-test` uses a fake Claude stream, so it checks `events.ndjson`, polling, status, and stop without spending model quota.

## Write scope and acceptance

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" preflight-write-scope --cwd /path/to/project --allow src --deny .env --max-diff-lines 800
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" check-write-scope --cwd /path/to/project
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" verify-run --run-id <run_id> --test-command "pytest"
```

If write scope is blocked, Codex should not accept the worker result.

## Queue, usage, and upgrades

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" queue-submit "Review this repo" --role review --priority 100
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" queue-tick --max-concurrent 3
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" queue-status
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" queue-policy --max-concurrent 3 --default-timeout-seconds 900 --apply
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" model-registry --refresh --apply
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" local-policy --preference development=GLM5.2 --preference multimodal=qwen3.7-plus --apply
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" score-worker --run-id <run_id>
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" prompt-pack --list
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" render-prompt --template repo-audit --task "Audit install safety"
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" usage-summary --write-report
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" benchmark-suite
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" upgrade-check --apply
```

Queue jobs use `queued`, `running`, `done`, `failed`, `timed_out`, and `cancelled` states.
