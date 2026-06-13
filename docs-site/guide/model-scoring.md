# Model scoring

The orchestrator scores local models found in CCSwitch.

The score is a local heuristic. It is not a paid benchmark run.

## What gets scored

Each discovered model receives scores for:

| Key | Meaning |
| --- | --- |
| `code` | Coding and refactoring fit |
| `long_context` | Large repo and long prompt fit |
| `reasoning` | Planning and review fit |
| `speed` | Expected response speed |
| `stability` | Expected reliability |
| `cost` | Cost or quota friendliness |
| `tool_use` | Agent and tool workflow fit |
| `multimodal` | Image or mixed input fit |

Then each role receives a weighted score.

For example, implementation weighs code and reasoning more heavily. Ops weighs stability, tools, speed, and cost more heavily.

## Run scoring

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" score-models
```

Write score and routing reports:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-reports
```

## Auto routes

The default policy can use aliases like:

```json
{
  "code_strong": "auto:implementation",
  "review_strong": "auto:review",
  "fast": "auto:testing"
}
```

This means the orchestrator picks the highest local role score from the models present on that machine.

## How to improve routing

1. Add a stronger model to CCSwitch.
2. Rerun `score-models`.
3. Rerun `write-auto-policy`.
4. Rerun `workflow-plan`.

The orchestrator does not mutate global CCSwitch state. It only reads profiles and injects the selected provider settings into the worker process.
