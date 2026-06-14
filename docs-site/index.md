---
layout: home

hero:
  name: Make Plus feel like Pro
  text: Claude Code Orchestrator Skill
  tagline: Codex stays in control. Claude Code workers run through CCSwitch and local model routing.
  image:
    src: /assets/cover.png
    alt: Claude Code Orchestrator technical cover
  actions:
    - theme: brand
      text: Get started
      link: /guide/getting-started
    - theme: alt
      text: Chinese docs
      link: /zh/

features:
  - title: Codex as controller
    details: Keep planning, review, and final judgment in Codex while workers handle scoped tasks.
  - title: Claude Code as worker
    details: Launch external Claude Code runs through CLI or MCP, with logs saved for review.
  - title: CCSwitch as router
    details: Read configured profiles, score available models, and pick the best fit per role.
  - title: Workspace governance
    details: Keep runs, reports, dashboards, archives, rollback notes, templates, and policies under .agent-workspace.
  - title: Safe by default
    details: Plan mode, redacted secrets, conservative write rules, and explicit run metadata.
---

## What this project is

`claude-code-orchestrator-skill` is a Codex Skill with a bundled MCP server and CLI.

It helps Codex use Claude Code as an external worker, route that worker through CCSwitch profiles, and keep every run visible enough to audit.

The core idea is simple:

| Part | Job |
| --- | --- |
| Codex | Brain, controller, reviewer, final decision maker |
| Claude Code | External worker process |
| CCSwitch | Local profile and model router |
| MCP | Tool interface that Codex can call |
| Run logs | The ledger for what each worker did |

Start with [Get started](/guide/getting-started), then wire the [MCP server](/guide/mcp) and learn the [multi-agent strategy](/guide/multi-agent).
