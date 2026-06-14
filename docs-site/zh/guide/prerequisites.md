# 前置条件

这套 Skill 真正好用之前，你需要先准备五样东西。

## Codex

Codex 是总控。

它负责计划任务、调用 MCP 工具、启动 worker、检查日志、看 diff，并给出最终结论。

## Claude Code

Claude Code 是外部执行进程。

orchestrator 会用选好的角色、prompt、权限模式和 provider 环境变量启动 `claude`。

先确认命令可用：

```bash
claude --version
```

也可以指定自定义路径：

```bash
export CLAUDE_CODE_BIN="/path/to/claude"
```

Windows：

```powershell
$env:CLAUDE_CODE_BIN = "C:\Path\To\claude.exe"
```

## CCSwitch

CCSwitch 是本机 profile 和模型路由器。

orchestrator 只读 CCSwitch 配置，不会改你的全局 CCSwitch 状态。它只把选中的 provider 环境变量注入到本次 Claude Code 进程里。

会检查这些位置：

- `$env:CCSWITCH_HOME`
- `$env:USERPROFILE\.cc-switch`
- 当前用户 home

## CCSwitch 里有多个模型

建议配置多个 Claude-compatible 模型。

模型越多，角色调度越有价值：

| 模型类型 | 适合做什么 |
| --- | --- |
| 强推理模型 | 架构、审查、安全 |
| 强代码模型 | 实现、重构 |
| 快速低成本模型 | 快速检查、小任务规划 |
| 稳定审查模型 | 风险、测试、兼容性 |
| 备用模型 | 主路由缺失时兜底 |

加完模型后重新运行：

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" score-models
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-auto-policy
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-reports
```

## Python 3.10+

内置 CLI 和 MCP Server 都是 Python 程序。

检查：

```bash
python --version
```

如果你的系统用 `python3`，示例命令里也改成 `python3`。
