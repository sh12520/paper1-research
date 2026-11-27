# OPV2V 共享计算争用诊断

**状态 BLOCKED_MISSING_CONCURRENT_WORKLOAD。** 在已有记录中没找到能够进入本任务的并发或连续检测业务片段。合格任务与配对均为 0，确认的争用超期个案为 0 条证据。真实争用超期和未归因真实超期的发生数均无法估计。

## 输入选择与查证结果

先核对独立结果 ID、原有应用任务释放、原场景输入和接收端 worker/CPU/GPU 映射。仅接受至少两个独立任务进入同一有证据的接收端资源的连续或并发片段。按原轨迹首个释放时刻升序取最早两段，同刻按轨迹 ID 排序，每段最多取前 30 个连续任务。固定原释放间隔与 45/50 ms 开发截止，不按是否超期筛选。

| 现有输入 | 查证 | 缺少的条件 |
|---|---|---|
| 官方 `datasets/opv2v-test-official/panel.jsonl` 与 `datasets/opv2v-test-official/OPV2V/pairing.csv` | 2169 个正式样本与 2169 个不同的场景×传感器时间戳对应，16 个场景。数据表保存点云与标注同步关系 | 没有应用任务释放时间、绝对截止和接收端算力拓扑。多车点云可服务同一个 ego 输出 |
| `results/opv2v-formal/per-frame/` 与原 runner | 一个场景时间戳一个原生 ego，`run_opv2v_formal.py:155` 选择 receiver，主循环逐样本、batch size 1 | 各帧输出没有重叠业务释放或占用方 ID |
| `results/opv2v-r26/screen/run.json`、`results/opv2v-r26/screen/completion.json` 和原 80 条回执 | 逐帧封存的真实 GPU 服务时间，开发抽样，R2.6 串行处理各帧 | 没有跨任务共同时钟、共享调度事件或原并发输入 |
| `results/opv2v-r25/live-overlap/completion.json` | 一个真实帧在接收和检测两条 CUDA stream 上有阶段计时重叠 | 两个输出是同一 ego 同一帧的首检和完整状态，不能作为独立任务。主机计时器复放到达 |
| `results/opv2v-r2-order-cpu-dev-repeat/` | 早期排序 CPU 开发脚本最多派发两个进程，五个新帧各来自不同场景。封存结果只有每进程整段墙钟以及帧内模型时序 | 无业务释放轨迹、同一接收端映射、进程共同时钟阶段与资源占用、按期隔离基线 |
| `results/opv2v-r24/report.json`、`results/opv2v-r21-pipeline/summary.json` | R2.4 调度的是单帧前缀版本。R2.1 的 167 是 35 ms 下帧内模型接收队列造成的**包**超期 | 无跨任务占用证据 |

预检 000068 的两车本地输出按顺序执行，协同只运行一个指定接收方向。没有将它或 80 帧抽样面板组装成并发负载。

## 实际入口、计量和版本

- 历史 systemd 原始启动命令见 `RUN_MANIFEST.json`。子入口 `scripts/run_opv2v_r26.py:255`，逐样本循环从第 273 行开始。第 189 行的 `evaluate_frame` 逐帧执行 `profile_ingress`、等价核验及 `profile_tail`。
- `scripts/opv2v_r25_pipeline.py:33,60,98` 执行解析、搬运及缓存散写。第 169 行的 `receiver_from_cache` 执行融合与检测头，再把输出搬回主机，进入第 233 行的 CPU 候选预筛、框解码和旋转 NMS 路径。
- `scripts/report_opv2v_r26_resources.py` 读取封存回执，调用 `scripts/report_opv2v_r25.py:93` 的 `pipeline_trace`。其 CPU/GPU 队列随着每一帧重新创建。真实服务秒表和基于 100 Mbps、RTT 10 ms、256 KiB 的模型到达及队列位置分开。没有给模型链路、输入就绪或完成位置补造主机绝对时间。
- 历史实测 GPU 为 RTX A6000 物理卡 1（`GPU-98963153-f8e3-c0d2-23b7-be180ff41808`），CUDA 测次及驱动信息保留在清单。每次接收测时 2 个 Torch CPU 线程、3 次重复。BlindMap 版本 `075b2c7120277a619f41bc49a58e3905ffad7aa7`。历史根仓运行时 HEAD 未记录。`35da85d5b11c90e508f555d6f8348910a86982be` 是事后快照，历史 GPU runner 的封存摘要与其对应文件吻合。
- 本轮在 Ubuntu 用标准库读取并校验旧档案，探测 GPU 状态，未启动模型或改动历史。实际命令、输入摘要、当前硬件与环境均见清单。

## 45/50 ms 配对与可归因性

| 截止期 | A/B/C 历史帧内回放超期数，各以 80 帧为分母 | 本轮 SHARED / ISOLATED / EDF |
|---|---:|---|
| 45 ms | 80 / 73 / 43 | NOT_RUN / NOT_RUN / NOT_RUN |
| 50 ms | 64 / 41 / 20 | NOT_RUN / NOT_RUN / NOT_RUN |

回放计数只反映各自检测的截止表现，没有纳入真实共享任务的分母。最接近条件的案例在 50 ms 回放中只晚约 0.038 ms，等待者和占用者均为同一检测的特征分片。真实重叠探针也没有记录到完整状态等首检的情形。两条代表时间线及原阶段事件已保存。

EDF 未达到启动条件。原帧内模拟队列不代表共享接收业务调度，因而无法检验原调度和 EDF 是否等价。EDF 救回数、新增超期数、未交付、按期回退、AP70、字节和排队时延的策略差均为 NOT_AVAILABLE。历史 C 帧的应用层字节及结果摘要保存在配对表的历史列。

## 仍需的输入

- 按接收业务记录的稳定 task_id、输入标识、原 task_release 与 absolute_deadline。
- 不同 task_id 到同一接收端 worker、CPU 核/线程池、GPU 或 stream/队列的映射。
- 同一时钟上的 last_fragment_rx、feature_ready、各阶段 runnable/enqueue/start/finish、占用方 task_id、result_ready。
- 保留相同传输和回退的隔离对照，以及任务级本地回退就绪记录。

`TASK_TIMELINES.jsonl` 含 80 条 R2.6 单帧记录和 1 条 R2.5 单帧重叠记录。保留阶段原数据与独立时钟域。配对 CSV 保留历史帧×截止期共 160 行用于定位原始记录，三组实测字段均注明未运行或缺失。应先取得带完整独立任务标识和共享映射的既有轨迹，再检验资源占用、关键路径等待和隔离及时性是否同时成立。
