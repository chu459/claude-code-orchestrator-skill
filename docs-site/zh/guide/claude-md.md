# CLAUDE.md

Claude Code 可以读取项目级 `CLAUDE.md`。

orchestrator 可以帮你生成一个，让每个 worker 启动前就知道自己的角色和边界。

## 创建一个

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-claude-md --cwd /path/to/project --role implementation
```

审查角色：

```bash
python "$CC_ORCHESTRATOR_HOME/cc_orchestrator.py" write-claude-md --cwd /path/to/project --role review
```

通过 MCP，Codex 可以调用：

```text
cc_write_claude_md
```

## 它会告诉 worker 什么

生成的文件会告诉 Claude Code：

- Codex 是总控、规划者、审查者和最终决策者。
- Claude Code 是外部 worker。
- worker 本次只有一个指定角色。
- 不要打印密钥。
- 不要执行危险命令，除非用户明确要求。
- 不要回滚无关的用户改动。
- 清楚报告进度和验证结果。

## 已有文件会被保护

如果 `CLAUDE.md` 已经存在，命令会保守处理。

| 选项 | 行为 |
| --- | --- |
| 默认 | 拒绝覆盖已有的非托管文件 |
| `--append` | 追加受管理的 orchestrator 区块 |
| `--force` | 先写带时间戳的备份，再替换文件 |

## 推荐流程

1. Codex 先规划任务。
2. Codex 给选中的角色写 `CLAUDE.md`。
3. Codex 通过 CLI 或 MCP 启动 Claude Code。
4. Claude Code 按角色规则执行。
5. Codex 审查日志、diff 和验证结果。
