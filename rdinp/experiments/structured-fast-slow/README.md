# RDINP 结构化限时意图仿真

第一步使用 Python 离散事件模型比较四种策略。结果属于开发对照。原 G1-A 按原判定封存，正式多档消息和状态机留待下一阶段验证。当前结果见[修正复算与快切归因](STEP1_REVIEW.md)，首批对照见[历史报告](STEP1_REPORT.md)。

## 复现

安装 Python 3.11 或更高版本。标定使用 Pillow，绘图使用 Matplotlib。以下命令从仓库根目录运行，结果目录须为新目录。

~~~bash
python -B rdinp/experiments/structured-fast-slow/test_sim.py -v
python -B rdinp/experiments/structured-fast-slow/run.py --out rdinp/experiments/structured-fast-slow/runs/step1-repeat
python -B rdinp/experiments/structured-fast-slow/audit.py rdinp/experiments/structured-fast-slow/runs/step1-repeat
python -B rdinp/experiments/structured-fast-slow/analysis.py rdinp/experiments/structured-fast-slow/runs/step1-repeat
~~~

[标定程序](calibrate.py)在传入历史三张样图的目录后执行 CPU 测量。[标定数据](calibration.json)附源图摘要、环境、预处理和逐次计时。复现开发对照直接使用这份标定数据，避免计时抖动改变输入。

## 首批复核与机制对照

历史 r01 的源码与证据保存在提交 6954a87d。其四组结果采用实时队列近似。复核遇到三项会影响比较的模型差异。

- 按 FIFO 找到可用执行槽后，队首任务的等待为零。后续任务保留在队列中，继续占用各自的未来执行时段。
- 终端依据已收到回执携带的队列快照作切档判断。快照在边缘处理提交时采样，回执加计 32 字节。各方法使用同一带延迟的无线速率观测。
- 被动重协商在边缘持有完整主档输入时，可以复用同任务图像。终端收到新代际回执后经同一链路发送 64 字节启动令牌，链路计入实际发送及重传。此路径跳过重新上传和预处理。

修正组仍使用全部 810 个原配对输入。运行和检查如下。

~~~bash
python -B rdinp/experiments/structured-fast-slow/test_resource_views.py -v
python -B rdinp/experiments/structured-fast-slow/run.py --causal-resource-view --out rdinp/experiments/structured-fast-slow/runs/step1-causal-repeat
python -B rdinp/experiments/structured-fast-slow/audit.py rdinp/experiments/structured-fast-slow/runs/step1-causal-repeat
python -B rdinp/experiments/structured-fast-slow/analysis.py rdinp/experiments/structured-fast-slow/runs/step1-causal-repeat
python -B rdinp/experiments/structured-fast-slow/run_attribution.py rdinp/experiments/structured-fast-slow/runs/step1-causal-repeat --out rdinp/experiments/structured-fast-slow/runs/step1-attribution-repeat
~~~

归因比较将初始轻量档准入和承诺后切档分别置为开或关，形成四个组合。所有组合保留结构化控制消息大小、本地预留、同一任务与代际守卫。主要对照是完整方案与仅靠初始准入选档的方案。按全部任务汇总，并报告 400、600、800 ms 各截止期的配对差异。其他三个差值及交互项用于判断两项机制是否叠加。复算完整结构化方案时，要求逐运行汇总与该版本四组首批结果完全一致。原场景与种子用于工程归因，区间用于描述稳定性。

## 输入与参数

- 每场景 10 个种子。10 秒内按带标记的泊松过程释放任务，8 个终端共享 2 个非抢占、先到先服务的边缘槽。每个终端有独立的本地串行执行队列。名义负载为 0.4、0.7 或 0.9，按主档槽位时间 145 ms 换算到达率。实际槽占用率随任务和方法变化。
- 上传的图像、输出、处理和预处理来自三张历史样图上的同一 Pillow 边缘检测器。主、轻量、本地档为 512²、384²、256²。以逐图和主档的软 Dice 相似度记质量，超过截止的结果效用为零。轻量档在上传前启用可节省 PNG 上行载荷。上传后、计算前改轻量档仍保留已经发送的字节，输出和服务耗时按标定轻量档近似。
- 主档边缘服务按 145 ms 量级建模，逐图 CPU 时间及轻量档 CPU 时间采用同一倍率。145 ms 是历史授权后槽位占用的工程量级，轻量档 slot 实测仍待单列。端侧预处理和本地档使用本机 CPU 标定值。端侧在截止前 55 ms 锁定边缘结果的采用并发起本地兜底，尾部余量是开发设定。
- 共享下行前传重放 5G-LENA 的 T1 容量事件，仿真中按 5 秒周期重复。空口使用上下行 FIFO 共享队列，基准 24／36 Mbps。在 T1 低容量段另施加 0%、50% 或 75% 的空口速率扰动。以 4 ms 为时间格建模分向突发故障，坏状态窗的长期占比设为 0%、5% 或 15%，平均坏段 36 ms。坏状态内触及的空口数据块失效。实际丢失率随发送时刻和调度而变化。每次发送的传播为 4 ms 加 0–3 ms 时间索引抖动。
- 模型以至多 8 KiB 数据块进入链路队列，每块 32 字节公共头。失败块最多重试两次，重试间隔为发送结束后 24 ms。向下发送的业务及控制经过前传和空口。控制消息与业务数据共享队列并占用容量。此处有实际容量事件的模型回放，也有单独设置的空口条件。
- 截止期取 400、600、800 ms。对负载、空口速率跌幅、坏状态窗占比和截止期做完整交叉。四策略每次读取同一任务序列、场景参数和分向、按时间索引的信道状态。每场景和种子的共同输入摘要保存在逐任务及逐运行表。

## 决策与统一统计

| 策略 | 采用规则 |
| --- | --- |
| Fixed-Intent | 仅尝试主档。确认失败或不能按时完成计未交付。 |
| Reactive-ReNeg | 先申请主档。准入被拒或估计不可按期时，可再申请一次相同轻量档。边缘计算前发现不可行时先通过控制消息请求修订。到回退点仍未采用则本地执行。 |
| Static-Fallback | 仅申请主档，采用同一回退时刻与本地档。 |
| Structured-RDINP | 首轮申请携带主、轻量和本地条款。慢环可准入可行的边缘档。按条件在上传前或边缘执行前转入已承诺的轻量档，到回退点仍未采用则本地执行。 |

慢环用意图／决策和提交／回执两次请求响应抽象协议。各方法共享同一因果可行性估算、队列观测、消息处理延迟和数据块重传规则。结构化意图的额外条款有额外字节，修订也有额外消息。当前控制体大小及 1 ms 权威响应处理成本为模型参数。空口速率观测有采样延迟，队列摘要按当前可读计数建模。仿真将结果按任务、代际和严格截止期做采用守卫。未收到提交回执的任务执行共同的重传及回退规则。

按全部释放任务计算主档、轻量、本地与未按期四类互斥比例，并报告有效效用、空口控制及业务字节、发起的请求响应轮次和协商用时。期限 SLA 将允许的本地档计为按期交付。若业务要求边缘质量，可用表中主档加轻量档比例单独核对。协商时间计已开启的轮次到结束、失败或截止。结构化机制初始轻档准入、上传前切档和计算前切档分开计数。边缘活跃时长、入队见忙和前传队列用于判断资源暴露。

总览按已释放任务汇总。配对差值以种子为重采样单位，在每次重采样中保留同一普查网格的所有同种子运行。百分位区间用于探索不同设置下的稳定性。用于第一批决策的是整体机制对照，慢环多档准入和承诺后的快切对比留待机制归因测试。
