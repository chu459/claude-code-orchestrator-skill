# 中文文档入口

这个项目的定位很直接：

> Make Plus feel like Pro.

它让 Codex 当总控，让 Claude Code 当外部 worker，让 CCSwitch 负责本地模型路由。

## 先看这些

- [Get started](/guide/getting-started): 安装和自检。
- [Prerequisites](/guide/prerequisites): Codex、Claude Code、CCSwitch、多模型配置、Python。
- [MCP setup](/guide/mcp): 把工具接进 Codex。
- [CLI reference](/guide/cli): 常用命令。
- [Model scoring](/guide/model-scoring): 本地模型评分和自动路由。
- [Multi-agent strategy](/guide/multi-agent): 多 Agent 策略。
- [CLAUDE.md](/guide/claude-md): 给 Claude Code worker 写项目规则。
- [FAQ](/faq): 常见问题。

## 一句话理解

不要让最强模型干所有杂活。

Codex 负责判断、拆解、验收。

Claude Code 负责执行。

CCSwitch 负责把不同 worker 分配到更合适的模型上。

每次运行都留下日志，方便 Codex 回看和验收。

## 最短启动

先安装 Claude Code 和 CCSwitch，并在 CCSwitch 里配置多个 Claude-compatible 模型。

然后把这句话交给 Codex：

```text
Install the Codex Skill and MCP server from https://github.com/chu459/claude-code-orchestrator-skill. Put the Skill at ~/.codex/skills/claude-code-orchestrator, wire the bundled MCP server into Codex config.toml, run selftest, healthcheck, score-models, and show me the selected multi-agent routing plan. Do not print secrets.
```

安装后跑：

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" selftest
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" healthcheck
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" score-models
```

如果你想看 worker 实时窗口，用：

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" run-visible "Inspect this project" --role architecture
```
