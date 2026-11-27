# 全局导航走查

走查以 `origin/main` 的 `43ec8f054054b715e2a562adeac0d43ae8f73593` 为基线。按默认稀疏检出的入口查阅，必要时用 `git show` 按文件读取归档。在 Ubuntu 上以 Python 标准库核对原表和个案。热缓存核对用时 0.05 秒，峰值 RSS 13,312 KiB，执行了两组已有记录的只读检查。

## 1. 当前路线、边界与下一验证

从 [AGENTS.md](../../AGENTS.md) 到 [当前推进](../../docs/current-research.md)，再读 [研究关系](../../docs/research-map.md) 和 [全局索引](../../docs/research-index.md)。现行优先级是 RDINP 的限时意图协商与边缘服务履约，阶段为导师审阅与问题验证。现有开发结果覆盖本机 Caddy、HTTP、SQLite 和受控故障。下一次决定性验证需要实际业务及 SLA、一条把授权到采用或回退连在一起的原运行轨迹，以及匹配的强对照。保留查询、幂等、有限租约、唯一代际、执行端时限守卫和回退。

入口给 OPV2V 保留了并行位置和历史证据，但深一层才看见它的独立决策。默认的复现提示只引到 RDINP 和 CS-ODS。按该提示读下去，会先遇到 OPV2V 的资源敏感性和并发受阻摘要，仍难发现 R1 的全量反馈反例、R2 的精确优化和可复用的自动化。将本方向加为可操作的开发分支足以补齐这一层证据。共享队列受阻应继续约束本方向的调度主张。

## 2. 从结论下钻到两种原始记录

### OPV2V 的完成覆盖与证据类型

从 [关键证据](../../docs/evidence-index.md) 打开 [R2.6 资源回放报告](../../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/result_summary.md)，再按 `scenario=measured_at_100` 查 [条件表](../../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/artifacts/resource-sensitivity-summary.csv) 和 [逐帧表](../../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/artifacts/resource-sensitivity-frames.csv)。逐行汇总核对了 45 ms 的 37/80 和 50 ms 的 60/80。开发面板 80 帧、16 场景，接收阶段使用历史 CUDA 实测计时，完整输出时间以模型链路及帧内资源回放计算。

抽查 `2021_08_23_21_07_10/000097/160`。尾包模型到达 26.492480 ms，完整结果 50.037986 ms，`passes_50ms=0`。用同一帧及 `deadline_ms=50` 对到 [队列诊断配对表](../../archive/v2x-development/queue-diagnostic/PAIRED_TASK_RESULTS.csv)，完成时间一致，应用层特征和封装共 181,156 B、控制消息 0 B。任务 ID 为 `NOT_AVAILABLE`，三组对照全为 `NOT_RUN`。对应的 [时间线](../../archive/v2x-development/queue-diagnostic/REPRESENTATIVE_TIMELINE.md) 将 0.167289 ms 等待定位到同一帧相邻分片。

已共享的资源回放 JSON、队列代表时间线分别与原工作区的对应文件 Git blob `8587e820bed778ae8ab04d1cafffd591851fff44`、`65b4e8f9f171e95f8b78bc68dbc4148af2d3d978` 一致，可直接复用。主线归档保留了逐帧时间线记录，不过报告所指的诊断 `RUN_MANIFEST.json` 与 GPU 原回执 `results/opv2v-r26/screen/per-frame/1332.json` 没有随原归档导入。原运行命令、代码绑定与单次测量出处应在本方向的 [证据页](EVIDENCE.md) 提供路径或可分享摘录。

### RDINP 执行点验证的可追溯性

通过 [DEV04 报告](../../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/业务代理执行对照与下一步证据.md)，从全局证据索引给出的 [转发延迟配对表](../../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/forward_delay_20261127-140016/summary.json) 下钻到 [执行点守卫个案](../../archive/genspace/PAPER1_TOPIC_APPROVAL_20261127/SERVICE_WORKER_DEV_04/forward_delay_20261127-140016/actuator_gate/result.json)。个案等于汇总中的 `actuator_gate` 项，记有拒绝时间、执行点调用状态和真实后端摘要。发送端单独检查时，执行点收到的更新返回 HTTP 200，截止后 85.4512 ms 读回 A 后端。执行点守卫在配对用例阻止调用，独立读回保留初始后端摘要。业务读回使用真实本机 HTTP 后端，转发延迟由受控注入产生，发生频率及真实服务收益仍待业务轨迹。旧报告的若干原始盘链接在其他机器不可用，证据索引的相对链接提供了可核对副本。

## 3. 从历史失败筛选下一线索

[历史经验第 3 项](../../docs/research-lessons.md) 已记录多车输入与同帧并行的局限。R2.5 的接收和检测重叠发生在同一帧，R2.6 的帧内队列每帧重新建立。R1 的接收者需求反馈在现有对照中也未达到收益门槛。应保留这两类结果，一个提示先核对基线，另一个约束可以归因的延迟范围。 [本地证据](EVIDENCE.md) · [队列诊断报告](../../archive/v2x-development/queue-diagnostic/QUEUE_DIAGNOSTIC_REPORT.md)

从 [文献入口](../../literature/README.md) 的 V2X 条目取 `xu2022opv2v`，题名、作者、ICRA 2022 和 arXiv 号与共享 BibTeX 对上。原文 §III-A 将 10 Hz 定义为传感器记录率，§IV 的示例融合流程以选定 ego 为接收端。固定的传感器时间戳与以同一时钟记录的接收任务释放是两个字段。由此可知，用一帧的多车辆记录或由采样率重建的到达间隔，无法补齐本次争用诊断所缺的任务证据。 [共享 BibTeX](../../literature/references.bib) · [OPV2V 作者原文](https://arxiv.org/html/2109.07644v5)

**候选问题。** 用精确前置计算和去重建立单任务服务时间基线后，真实共享执行是否仍出现受局部队列策略影响的迟到？需要同一接收端至少两个独立任务的释放、绝对截止、输入就绪、资源占用、结果就绪与采用时间，以及等输入的共享／隔离对照。缺原轨迹时保留受阻状态。若取得轨迹后，隔离也不能按期，先排查尾包、计算和截止本身。若可归因的损失由同观测下的简单局部调度解决，结束该项协商必要性验证。RDINP 的受控代理经验可以复用到“结果就绪”和“实际采用”的记账，协议效果仍需各自验证。

## 4. 新方向从哪里被发现

| 查阅需求 | 入口 |
| --- | --- |
| 从全局进入后识别开发方向和阶段 | [仓库首页](../../README.md) 或 [研究分支目录](../README.md) → [OPV2V 方向首页](README.md) → [当前状态](CURRENT.md) |
| 复用流程或读证据 | [OPV2V 证据](EVIDENCE.md) · [Autoresearch](autoresearch/README.md) · [文献版本](REFERENCES.md) |
| 继续查早期原始表 | [全局证据索引](../../docs/evidence-index.md) → [已有 OPV2V 档案](../../archive/v2x-development/README.md) |

建议保持全局当前路线的优先级。在跨方向索引的下一次维护中，为关键证据行标记模型时钟、历史实测计时、共享运行或缺失证据。给包含历史原机链接的报告加一条可迁移证据索引反向入口，避免改动原档案。默认稀疏检出缺少的归档可以按全局索引补取。只查本例时用以下命令读取指定提交，仅需要相应 blob。

```bash
git show 43ec8f054054b715e2a562adeac0d43ae8f73593:archive/v2x-development/latest-opv2v/latest_run_20261126_232310/artifacts/resource-sensitivity-frames.csv |
  awk 'NR == 1 || /2021_08_23_21_07_10\/000097\/160,measured_at_100/'
```

本次 Ubuntu 检出另发现一个入口问题。应用仓库建议的稀疏路径后，工作树缺少根目录的 `AGENTS.md` 和 `README.md`，但 Git 对象可读取。先用 `git show HEAD:AGENTS.md` 继续走查，随后用 `git sparse-checkout add AGENTS.md README.md .gitignore .gitattributes CONTRIBUTING.md` 恢复根入口。若其他设备遇到同样情况，可将这条补取命令附在稀疏检出说明后。
