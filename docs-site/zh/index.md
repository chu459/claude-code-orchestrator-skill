---
layout: home

hero:
  name: 让 Plus 用出 Pro 的效果
  text: Claude Code Orchestrator Skill
  tagline: Codex 当总控，Claude Code 当执行层，CCSwitch 负责本地模型路由。
  image:
    src: /assets/cover.png
    alt: Claude Code Orchestrator 技术封面
  actions:
    - theme: brand
      text: 快速开始
      link: /zh/guide/getting-started
    - theme: alt
      text: 更新日志
      link: /zh/changelog
    - theme: alt
      text: English
      link: /

features:
  - title: Codex 当总控
    details: 让 Codex 负责计划、调度、审核和最终判断。
  - title: Claude Code 当工人
    details: 通过 CLI 或 MCP 启动外部 Claude Code worker，并保存日志。
  - title: CCSwitch 当路由器
    details: 读取本机模型配置，按角色选择更合适的模型。
  - title: 工作区治理
    details: 把 runs、reports、dashboard、archives、rollback、templates、policies 收进 .agent-workspace。
  - title: 默认更安全
    details: 默认计划模式、密钥脱敏、写入范围约束、每次运行都有记录。
---

## 这个项目是什么

`claude-code-orchestrator-skill` 是一个 Codex Skill，里面自带一套 MCP Server 和 CLI。

它帮助 Codex 把 Claude Code 当成外部 worker 使用，再通过 CCSwitch 调用你电脑上已经配置好的模型。

核心思路很简单：

| 部分 | 作用 |
| --- | --- |
| Codex | 大脑、总控、审查者、最终决策者 |
| Claude Code | 外部执行 worker |
| CCSwitch | 本地模型和 profile 路由器 |
| MCP | Codex 可以直接调用的工具接口 |
| 运行日志 | 每个 worker 做了什么都能回看 |

先看 [快速开始](/zh/guide/getting-started)，再接入 [MCP](/zh/guide/mcp)，然后读 [更新日志](/zh/changelog) 和 [多 Agent 策略](/zh/guide/multi-agent)。
