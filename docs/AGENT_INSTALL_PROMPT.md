# One-Line Agent Install Prompt

Copy this into Codex after Claude Code and CCSwitch are already installed:

```text
Install the Codex Skill and MCP server from https://github.com/chu459/claude-code-orchestrator-skill. Put the Skill at ~/.codex/skills/claude-code-orchestrator, wire the bundled MCP server into Codex config.toml, run selftest, healthcheck, score-models, init-workspace, workspace-status, and show me the selected multi-agent routing plan. Do not print secrets.
```

中文版:

```text
请从 https://github.com/chu459/claude-code-orchestrator-skill 安装这个 Codex Skill 和自带 MCP。把 Skill 放到 ~/.codex/skills/claude-code-orchestrator，把自带 MCP 写进 Codex config.toml，然后运行 selftest、healthcheck、score-models、init-workspace、workspace-status，并把多 agent 路由策略展示给我。不要打印任何密钥。
```
