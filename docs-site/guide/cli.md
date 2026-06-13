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
