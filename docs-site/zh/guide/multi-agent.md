# 多 Agent 策略

项目目标很直接：

> 让 Plus 用出 Pro 的效果。

把最强模型留给判断，把更快或更便宜的 worker 用在明确子任务上，Codex 始终当总控。

## 运行模型

| 层 | 职责 |
| --- | --- |
| 大脑 | Codex 计划、调度、审查、决策 |
| 手 | Claude Code worker 执行明确任务 |
| 路由器 | CCSwitch 提供本地 profile 和模型 |
| 账本 | 每次 run 都留下 metadata、prompt、stdout、stderr |

## 默认角色

| 角色 | 用途 |
| --- | --- |
| `requirements` | 范围、非目标、验收标准 |
| `architecture` | 仓库地图、相关文件、实现计划、风险 |
| `development` | 主开发任务 |
| `testing` | 测试计划、边界场景、验证命令 |
| `review` | 发现问题、文件引用、可维护性 |
| `performance` | 运行耗时、IO、延迟、资源占用 |
| `compatibility` | Windows、macOS、Linux、shell、版本风险 |
| `documentation` | 教程、FAQ、示例、上手文档 |
| `automation` | CI、发布流程、打包检查 |
| `security` | 密钥、权限、命令风险、供应链 |
| `implementation` | 写入范围明确后的代码修改 |
| `ops` | 部署、日志、回滚、运行风险 |
| `multimodal` | 图片或混合输入任务 |

## 四阶段流程

1. 并行分析：需求、架构、安全、测试等角色先看任务。
2. 交叉审查：不同 agent 对比风险、范围、方案质量。
3. 执行：计划稳定、写入范围清楚后，再让 implementation 动手。
4. 总控总结：Codex 看日志、diff、测试和最终输出。

生成计划：

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" workflow-plan "Ship a safe refactor"
```

## 成本规则

不要让最强模型做所有小活。

强模型适合：

- 最终判断
- 架构分析
- 高风险审查
- 难取舍的问题

worker 模型适合：

- 仓库地图
- 测试设计
- 文档草稿
- 兼容性检查
- 审批后的明确实现

这就是这个项目存在的主要原因。
