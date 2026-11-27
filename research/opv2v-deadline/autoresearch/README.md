# Autoresearch 工作台

本地工作流已用于训练例证据审计、冻结输入预检和 OPV2V 逐帧续跑。协作副本保留可移植的回执管理器、可核验的真实历史回执，以及 OPV2V 监督和文献收集流程的源码档案。原工作流与阶段入口见 [执行与归档](WORKFLOW.md)。交接、单变量实验和独立复核可复用 [角色提示模板](protocols/PROMPTS.md)。

跨机器切换、项目技能和原机接续见 [工作导航](NAVIGATION.md) 与 [本地交接](local/README.md)。

## 最小验证

Linux、Python 3.10+ 和 GNU `sha256sum`。从仓库根目录运行统一只读检查。

```bash
python3 -B research/opv2v-deadline/autoresearch/scripts/check_shared_assets.py
```

统一入口验过 6 个原机交接文件和 11 个工作流文件的摘要、DAIR 封存回执、R1 一帧四策略包时钟，以及 16 份结果与 18 个截止表单元。本次 Ubuntu Python 3.10.12 实测墙钟 0.20 s、峰值 RSS 22,940 KiB，退出码 0。

单项回执核对从仓库根目录执行。

```bash
cd research/opv2v-deadline/autoresearch
python3 -B scripts/research_harness.py list
python3 -B scripts/research_harness.py verify evidence-46 --attempt 20261124T153454170423Z-3541052b
```

`verify` 核对 [预约记录](experiments/research-harness/evidence-46/20261124T153454170423Z-3541052b/reservation.json) 的输入清单摘要、[回执](experiments/research-harness/evidence-46/20261124T153454170423Z-3541052b/receipt.json) 的内部摘要和 [封存产物](experiments/research-harness/evidence-46/20261124T153454170423Z-3541052b/evidence-46.json) 的文件摘要。原审计覆盖 138 条检测、366 条策略回放、46 帧缓存一致性。46 帧都来自单一基础设施批次的 DAIR 官方训练示例，独立验证覆盖为 0。协作副本由该回执校验追溯原输入，重新查验 138 条检测需另外取得预约记录中的原始日志。

`run TASK` 每次核验当前输入，包括检查器自身和 Python 版本。已有成功回执须匹配当前输入摘要并验证产物后才复用。缺件退出 2，失败或中断退出 1，成功退出 0。`cycle` 执行允许列表，即使某项阻塞仍可取得其它项的结果。恢复操作先获得独占锁，再把此前失去锁且无回执的尝试归档为 `interrupted`。

| 任务 | 缺件检查 |
| --- | --- |
| `evidence-46` | 路径与摘要见封存预约记录。按原相对路径补齐输入才可重新审计 |
| `dair-preflight` | 需原始 `scripts/audit_dair_validation_panel.py`、冻结协议和官方划分。历史检查覆盖 0/1,783，三个配对元数据表缺失。[原 readiness 产物](archive/receipts/dair-readiness.json) |
| `gpu-preflight` | 需原始 `scripts/run_blindmap_dair.py` 和主机 NVIDIA CLI。注册回调只请求 `--gpu-status`。原门槛为空闲显存至少 16,000 MiB、利用率至多 10%、温度至多 75°C、无已有计算进程。预检通过表示当时观测满足阈值 |

任务写入当前副本的 `experiments/research-harness/`。工程检查建议在临时副本执行，避免把后续各设备的日志混入共享分支。正式推理和服务的现行授权另行检查。

## 本次协作副本验证

从本分支树实际执行，Linux CPU、单进程、无模型载入或网络请求。以 GNU `time` 的 `elapsed_s` 记录墙钟。

| Python | 执行 | 实际结果 | 时间 / 峰值 RSS |
| --- | --- | --- | --- |
| 3.14.10 | `python3 -B scripts/research_harness.py list` | 三项允许任务，退出 0 | 0.09 s / 22,784 KiB |
| 3.14.10 | `python3 -B scripts/research_harness.py verify evidence-46 --attempt 20261124T153454170423Z-3541052b` | verified，退出 0 | 0.08 s / 22,784 KiB |
| 3.10.12 | `python3 -B scripts/research_harness.py list` | 三项允许任务，退出 0 | 0.05 s / 17,920 KiB |
| 3.10.12 | `python3 -B scripts/research_harness.py verify evidence-46 --attempt 20261124T153454170423Z-3541052b` | verified，退出 0 | 0.06 s / 18,176 KiB |
| 3.10.12 | 临时副本执行 `python3 -B scripts/research_harness.py run evidence-46` | 原始检测等 16 个输入缺失，blocked，退出 2 | 0.07 s / 18,432 KiB |
| 3.10.12 | 在临时副本对 `evidence-46.json` 追加换行后，执行相同 `verify` 命令 | Evidence files do not match receipt，退出 1 | 0.05 s / 18,432 KiB |

最后两项是回执机制验证。封存回执和原工程内容保持原样。[内容摘要](SOURCE_SHA256SUMS.txt)
