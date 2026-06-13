# Multi-agent strategy

The project goal is practical:

> Make Plus feel like Pro.

Use the strongest model for judgment. Use cheaper or faster workers for scoped execution. Keep Codex in charge.

## Operating model

| Layer | Role |
| --- | --- |
| Brain | Codex plans, routes, reviews, and decides |
| Hands | Claude Code workers perform scoped tasks |
| Router | CCSwitch provides local profiles and models |
| Ledger | Each run leaves metadata, prompts, stdout, and stderr |

## Default roles

| Role | Use it for |
| --- | --- |
| `requirements` | Scope, non-goals, acceptance criteria |
| `architecture` | Repo map, likely files, implementation plan, risk |
| `development` | Main code development tasks |
| `testing` | Test plan, edge cases, validation commands |
| `review` | Findings, file references, maintainability |
| `performance` | Runtime, IO, latency, resource use |
| `compatibility` | Windows, macOS, Linux, shell, version risk |
| `documentation` | Tutorials, FAQ, examples, onboarding |
| `automation` | CI, release workflows, package checks |
| `security` | Secrets, permissions, command risk, supply chain |
| `implementation` | Scoped edits when write access is allowed |
| `ops` | Deployment, logs, rollback, runtime risk |
| `multimodal` | Image or mixed input work |

## Four-phase workflow

1. Parallel analysis: requirements, architecture, security, testing, and other relevant roles inspect the task.
2. Cross-review: agents compare risk, scope, and plan quality.
3. Execution: implementation runs only after the plan is stable and write scope is clear.
4. Controller summary: Codex reviews logs, diffs, tests, and final output.

Generate the plan:

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" workflow-plan "Ship a safe refactor"
```

## Cost rule

Do not spend the best model on every subtask.

Use it for:

- final judgment
- architecture
- risky review
- hard tradeoffs

Use worker models for:

- repo mapping
- test design
- documentation draft
- compatibility checks
- focused implementation after approval

This is the main reason the project exists.
