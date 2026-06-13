# Real-Time Progress Design

The current version stores every run under:

```text
scripts/cc-orchestrator/runs/<run_id>/
  metadata.json
  prompt.txt
  stdout.txt
  stderr.txt
```

## What works today

Use visible Claude Code windows when you want to watch an agent think and act:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run-visible "Inspect this project" --role architecture
```

Use `last-run` after any run:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" last-run
```

Tail logs on Windows:

```powershell
Get-Content "$env:CC_ORCHESTRATOR_HOME\runs\<run_id>\stdout.txt" -Wait
```

Tail logs on macOS/Linux:

```bash
tail -f "$CC_ORCHESTRATOR_HOME/runs/<run_id>/stdout.txt"
```

## Better live-progress idea

The next serious upgrade is a tiny progress bus:

1. Each agent writes `events.jsonl` while it runs.
2. MCP exposes `cc_watch_runs` and `cc_run_status`.
3. Codex reads the event stream every few seconds.
4. A terminal dashboard shows:
   - agent role
   - selected model
   - elapsed time
   - current phase
   - last stdout line
   - estimated cost class
   - timeout risk

## Why this matters

The whole point of the project is cost management:

- one strong model acts as the brain
- worker models act as hands
- Codex remains the manager
- logs make every worker auditable

No invisible magic. Every worker leaves a trace.
