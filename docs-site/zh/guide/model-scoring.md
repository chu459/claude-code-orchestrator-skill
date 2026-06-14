# 模型评分

orchestrator 会给 CCSwitch 里发现的本机模型打分。

这个分数是本地启发式评分，不是付费 benchmark。

## 会评哪些项

每个模型会得到这些分数：

| 字段 | 含义 |
| --- | --- |
| `code` | 写代码和重构能力 |
| `long_context` | 大仓库、长上下文能力 |
| `reasoning` | 规划和审查能力 |
| `speed` | 预期响应速度 |
| `stability` | 预期稳定性 |
| `cost` | 成本或额度友好度 |
| `tool_use` | Agent 和工具调用适配度 |
| `multimodal` | 图片或混合输入能力 |

然后每个角色会按权重得到一个总分。

例如，implementation 更看重代码和推理；ops 更看重稳定性、工具、速度和成本。

## 运行评分

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" score-models
```

写入评分和路由报告：

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-reports
```

## 自动路由

默认策略可以使用这样的别名：

```json
{
  "code_strong": "auto:implementation",
  "review_strong": "auto:review",
  "fast": "auto:testing"
}
```

意思是：orchestrator 会从当前电脑已有模型里，选出这个角色分数最高的模型。

## 怎么让路由更准

1. 在 CCSwitch 里加更合适的模型。
2. 重新跑 `score-models`。
3. 重新跑 `write-auto-policy`。
4. 重新跑 `workflow-plan`。

orchestrator 不会改全局 CCSwitch 状态，只读取 profile，并把选中的 provider 配置注入到本次 worker 进程。
