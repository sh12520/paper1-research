# 原机运行资料

本目录连接协作仓库里的只读检验与原工程的完整运行入口。OPV2V 模型依赖与推理环境、独立确认输入、各轮逐帧原结果继续保存在原工程。协作者先看[研究状态](../../CURRENT.md)、[证据](../../EVIDENCE.md)和[跨机工作流](../WORKFLOW.md)。

| 目的 | 协作仓库 | 完整原工程 |
| --- | --- | --- |
| 恢复上下文 | [导航走查](../../NAVIGATION_REVIEW.md) · [路线沿革](../../notes/local-history.md) | `AGENTS.md`、`docs/EXPERIMENT_MASTER_PLAN.md`、`docs/RESEARCH_GOAL.md`、`docs/PROGRESS.md`、`docs/DECISIONS.md` |
| 查任务与回执 | [Python harness](../README.md)，可直接核对封存的 `evidence-46` | `scripts/research_harness.py`、`scripts/research_harness_tasks.py`、`experiments/research-harness/<task>/<attempt>/` |
| 核对数据条件 | [DAIR 只读输入盘点](audit_dair_validation_panel.py) | `scripts/research_harness.py run dair-preflight`，带完整面板与遮挡辅助表门槛 |
| 核对原 OPV2V 进度 | [阶段回执摘录](../archive/receipts/opv2v-r26-supervisor-extract.json) · [证据](../../EVIDENCE.md) | `experiments/autoresearch/status.json`、`experiments/autoresearch/receipts/`、`results/opv2v-r26/screen/` |
| 查模型、权重和来源 | [文献与发布源](../../REFERENCES.md) · [证据来源](../../results/SOURCES.json) | 发布目录 `models/blindmap-tmc/`，上游固定版本 `075b2c7120277a619f41bc49a58e3905ffad7aa7` |
| 查冻结规则 | [DAIR 锁定原件](protocols/DAIR_FORMAL_VALIDATION.md) · [OPV2V R2.6 原件](protocols/OPV2V_R26_DEADLINE_FRONTIER.md) | `configs/dair-v2x/FORMAL_VALIDATION.md`、`configs/opv2v/R26_DEADLINE_FRONTIER.md` |

上述两份规则为历史冻结文档，对照组、样本和指标维持其冻结时定义。现行运行授权和状态从仓库约定及 [CURRENT.md](../../CURRENT.md) 核对。原工程著录 `docs/RESEARCH_HARNESS.md` 和 `docs/AUTORESEARCH_{OBJECTIVE,PROGRESS,DECISIONS}.md` 的版本摘要见 [WORKFLOW.md](../WORKFLOW.md)，便于比较阶段变化。

## DAIR 数据资格

从协作仓库根目录运行。设置 `SOURCE_ROOT` 为持有原冻结输入的项目。报告路径自选，需位于有权写入的原项目目录并尚不存在。

```bash
python3 -B research/opv2v-deadline/autoresearch/local/audit_dair_validation_panel.py \
  "${SOURCE_ROOT}/datasets/dair-full-official/cooperative-vehicle-infrastructure" \
  "${SOURCE_ROOT}/results/dair-collaborator-preflight.json" \
  --split "${SOURCE_ROOT}/configs/dair-v2x/val.json"
```

使用 Python 标准库，验证冻结 `val.json` SHA-256 与 1,783 个唯一 ID，再按原程序盘点车路配对元数据、传感器、标注和标定。保留逐帧遮挡辅助表状态。执行成功表示盘点完成。须查 `ready`、`missing_tables`、`official_occlusion_exists` 判定完整面板的原生评估是否具备条件。正式调度仍以原 harness 的 `native_entry_data_ready` 为准。原数据、冻结 ID 列表和新生成的机器路径报告留在原机。

本次移植验证在 Ubuntu 使用 Python 3.10.12 完成，墙钟 0.03 s、峰值 RSS 15,360 KiB、退出 0。输出 **0/1,783 帧、0 个场景、3 份元数据缺失**，所有非路径字段与历史封存报告相符。另用临时副本验证了冻结输入摘要不符时退出 2 且无输出、重复目的文件保留旧内容。这些检查只读数据和归档回执。 [历史资格结果](../archive/receipts/dair-readiness.json)

## GPU 与跨会话监督

原机的 GPU 预检只读取 NVIDIA 指标。历史保护门槛为空闲显存至少 16,000 MiB、利用率不高于 10%、温度不高于 75°C、无既有计算进程。曾有两张卡同时触发四项条件，保持 `blocked`。单次快照只描述采样时刻，运行中的检查由实际 worker 与现行授权约束。 [GPU 受阻回执摘录](historical-gpu-preflight.json)

从完整原工程可查看已有服务和证据。

```bash
systemctl --user status research-autoresearch.timer
systemctl --user list-units 'research-opv2v*' --no-pager
systemctl --user list-timers research-autoresearch.timer --no-pager
python3 -B scripts/research_harness.py status
```

[systemd 服务示例](systemd/research-autoresearch.service.example)与[计时器示例](systemd/research-autoresearch.timer.example)记录原方式，每五分钟进入一次低优先级、有时间上限的监督循环。示例用于审查或在持有完整原工程的机器上准备部署。把 `__SOURCE_ROOT__` 和 `__PYTHON__` 替换为当地项目目录及对应解释器，在临时目录用正式后缀保存，再执行 `systemd-analyze --user verify`。选择原工程下可写的运行日志目录。如果路径含空格，渲染时还需按 systemd 的字段语法引用参数。在 Ubuntu 对渲染后的原布局实际验证通过，墙钟 0.16 s、峰值 RSS 10,496 KiB、退出 0。协作检验未安装和启动用户服务。示例所指向的 `supervise` 会根据状态派发工作，需独立确认完整输入、GPU、工作流状态及运行授权。

[来源与 SHA-256](PROVENANCE.json)记录逐字节复制和可移植改写的映射，保留原件身份与共享文件摘要。
