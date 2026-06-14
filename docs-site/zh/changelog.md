# 更新日志

这里记录 Claude Code Orchestrator Skill 的主要版本变化。

## v0.5.0 - 工作区治理

- 新增 `.agent-workspace/claude-code-orchestrator`，默认收纳 Agent 生成的运行产物。
- 新增 `init-workspace`、`workspace-status`、`migrate-data`、`clean-workspace`、`archive-runs`、`repair-mcp-paths`、`folder-policy`。
- 每个工作区治理命令都补齐了对应 MCP 工具。
- 更新 worker prompt 和生成的 `CLAUDE.md`，让日志、报告、临时文件、回滚记录进入统一目录。
- 更新安装示例和文档，让不同电脑上的产物路径更稳定。

## v0.4.1 - 总控 checkpoint 和队列状态补强

- 新增滚动 `checkpoint-###.md`，用于长任务阶段总结。
- 新增工具调用去重摘要，比如 `Grep x7`、`Read x3`。
- `poll-run` 的 controller 模式默认写入压缩后的总控产物。
- 队列状态明确为 `queued`、`running`、`done`、`failed`、`timed_out`、`cancelled`。
- 改进本地 dashboard，看模型路由、时间线、日志、diff、风险和控制命令更清楚。

## v0.4.0 - Codex 总控系统

- 新增 `references/codex-controller-playbook.md`。
- 新增 Prompt Pack：仓库审计、Bug 修复、安全审计、前端打磨、测试生成、重构计划、发布检查。
- 新增压缩轮询、`cc_summarize_run`、`cc_compact_events`。
- 新增队列策略、模型能力库、benchmark 历史、本机偏好保留、worker 质量历史、失败模式识别。
- 新增时间线看板和每日检查 GitHub 更新的说明。

## v0.3.0 - 验收和安全运行

- 新增一键 `cc_verify_run`。
- 串起 diff 摘要、写入范围检查、密钥扫描、可选测试、Markdown 报告。
- 新增不消耗模型额度的 mock streaming 测试。
- 新增用量统计、升级检查、benchmark suite、MCP 自动注册。
- 新增 `version.json` 作为版本元数据来源。

## v0.2.0 - 实时 worker 控制

- 新增 `run-streaming` / `cc_run_streaming_agent`。
- Claude Code 使用 `--output-format stream-json --include-partial-messages` 启动。
- 新增 `poll-run`、`run-status`、`stop-run`。
- 新增角色团队、结果汇总、交叉审查、dashboard、报告导出、成本护栏、可视 worker 窗口。

## v0.1.0 - Skill、MCP、CLI、CCSwitch 基座

- 创建 Codex Skill 入口。
- 新增内置 MCP Server 和 CLI orchestrator。
- 新增 CCSwitch profile 发现和 Claude Code 二进制发现。
- 新增本机模型按角色评分和角色路由。
- 新增安全默认值、运行元数据、日志、`CLAUDE.md` 生成、UTF-8 输出处理、密钥脱敏。
