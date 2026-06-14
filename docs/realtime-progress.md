# Real-Time Progress

P0 live control is implemented.

Codex no longer has to wait for Claude Code to finish before seeing progress.

## Run Folder

Each streaming run writes:

```text
scripts/cc-orchestrator/runs/<run_id>/
  metadata.json
  prompt.txt
  stdout.txt
  stderr.txt
  events.ndjson
  pid.txt
```

`events.ndjson` is one JSON event per line.

Important event types:

- `run_started`
- `stream_worker_started`
- `process_started`
- `claude_stream`
- `stderr`
- `stop_requested`
- `stopped`
- `timeout`
- `process_exited`

## Start A Streaming Worker

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run-streaming "Inspect this project" --role architecture
```

The command returns immediately with:

- `run_id`
- worker pid
- selected profile/model
- log paths
- poll offsets

The launched Claude Code command uses:

```text
claude -p --output-format stream-json --verbose --include-partial-messages
```

## Poll One Run

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" poll-run --run-id <run_id>
```

`poll-run` defaults to controller mode and returns:

- current status
- active/alive flags
- elapsed time
- compact progress summary
- risk flags
- changed files
- timeline
- deduplicated tool-call summary
- latest checkpoint
- next offsets

For cursor-style polling, pass the returned offsets:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" poll-run `
  --run-id <run_id> `
  --stdout-offset 1200 `
  --stderr-offset 0 `
  --event-offset 3400
```

Use raw mode only when debugging:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" poll-run --run-id <run_id> --mode raw
```

To write the controller artifacts explicitly:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" summarize-run --run-id <run_id>
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" compact-events --run-id <run_id> --write-artifacts
```

This writes:

- `progress_summary.json`
- `latest_decision.md`
- `risk_flags.json`
- `changed_files.json`
- `tool_timeline.md`
- `checkpoints/checkpoint-###.md`

## List Active Workers

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run-status
```

This returns all active streaming workers.

To inspect one run:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" run-status --run-id <run_id> --include-output
```

## Stop A Worker

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" stop-run --run-id <run_id> --force
```

`stop-run` requires an explicit run id so Codex does not accidentally kill the wrong worker.

On Windows, the orchestrator uses `taskkill /PID <pid> /T` and adds `/F` when force is requested.

## Test Without Spending Model Quota

Use the fake stream test:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" mock-stream-test
```

It launches a mock Claude command and verifies:

- `events.ndjson` is written
- `poll-run --mode raw` returns event deltas
- `poll-run` returns compact controller progress and writes rolling checkpoints
- `run-status` sees an active worker
- `stop-run` can terminate a long mock stream

## Verify After Writes

For write-capable runs, use:

```powershell
python "$env:CC_ORCHESTRATOR_HOME\cc_orchestrator.py" verify-run --run-id <run_id> --test-command "pytest"
```

`verify-run` chains:

- diff summary
- write-scope check
- secret scan
- optional test commands
- Markdown report
- worker quality score

If write scope is blocked, Codex should not accept the worker output.

## MCP Tools

The same P0 loop is available through MCP:

```text
cc_run_streaming_agent
cc_poll_run
cc_run_status
cc_stop_run
cc_mock_stream_test
cc_verify_run
```

## Why This Matters

This is the difference between:

```text
wait for Claude Code to finish
```

and:

```text
Codex watches, polls, and stops workers in real time
```

That is the control layer needed for serious multi-agent work.
