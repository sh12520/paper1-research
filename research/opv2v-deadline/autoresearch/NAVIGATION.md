# 跨机器工作导航

从仓库根部的 [AGENTS.md](../../../AGENTS.md) 进入，按本轮任务选入口。

| 当前任务 | 先读 | 下一步 |
| --- | --- | --- |
| 接手论文 1 或核对方向优先级 | [全局当前推进](../../../docs/current-research.md) | 看 [OPV2V 当前判断](../CURRENT.md) 和各路线的授权边界 |
| 找到数值出处或停止条件 | [OPV2V 证据](../EVIDENCE.md) | 沿报告、结果表和案例 ID 下钻。两条实走路径见 [导航走查](../NAVIGATION_REVIEW.md) |
| 在另一台机器复核结果 | [Autoresearch 工作台](README.md) | 核验共享封存回执。计算与通信模型的最小复算见 [复现入口](../src/README.md) |
| 找原机状态或恢复已授权任务 | [本地运行交接](local/README.md) | 核对原项目目录、依赖、原输入哈希与最新回执。原实现见 [执行与归档](WORKFLOW.md) |
| 让 Agent 按现有流程接续 | [导航技能](../../../.agents/skills/paper1-navigate/SKILL.md) · [harness 技能](../../../.agents/skills/paper1-research-harness/SKILL.md) | 使用 [角色提示模板](protocols/PROMPTS.md) 分开受领、执行和复核 |

## 状态和档案

- `CURRENT.md` 与全局当前推进描述已登记的判断、证据门槛和后续范围。需要原机实时状态时，依本地运行交接读取当前尝试及队列。
- `EVIDENCE.md`、`results/SOURCES.json`、封存回执以及 `archive/` 可追溯已完成的实验。源码投影或模型回放保留各自来源。旧命令、旧提示和历史通过状态用于解释记录，开始新执行时以本轮授权和当前输入为准。
- 若案例缺独立任务释放、共同执行资源、占用事件或隔离配对，保留队列诊断的阻塞结论。原时间线可用于说明为何选择下一项测量。

## 稀疏检出定位

从 Git 根目录运行。把 `.agents` 加入稀疏目录以读取仓库技能。锥形模式同时保留根文件。已有非锥形检出可继续使用 `git show HEAD:AGENTS.md`，或按[原走查](../NAVIGATION_REVIEW.md)补取根文件。

```bash
git sparse-checkout set --cone .agents docs literature research rdinp csods
git show HEAD:archive/v2x-development/queue-diagnostic/REPRESENTATIVE_TIMELINE.md
```

第二条命令已在本分支的稀疏工作树核对，可直接读取未检出的归档文件。需要整组关联记录时，再用 `git sparse-checkout add archive/v2x-development/queue-diagnostic`。完整归档查找见[全局索引](../../../docs/research-index.md)。

Ubuntu 上使用 Codex CLI 0.171.0 的本地 `skills/list` 验证了两项技能都可从仓库发现，作用域为 `repo`，均已启用。没有启动模型会话。
