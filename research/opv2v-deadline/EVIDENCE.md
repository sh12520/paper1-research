# OPV2V 开发证据

此处的 R1、R2.3–R2.6 编号指本地方向。各轮的字母组别独立定义。OPV2V 是仿真车车感知，DAIR-V2X-C 才是原拟实采车路场景。证据区分真实模型输出、真实计算时间、网络模型回放和输入可用性核验。

## 需求反馈及发送方对照

R1 的 A 只发首包，B 按主动分数无反馈补包，C 用接收方稀疏需求反馈补包，D 用发送方前景信息补包。主条件为全 LiDAR BlindMap TMC epoch 37、2,169 帧、16 场景、每帧 256 KiB 应用消息硬预算、100 Mbps、10 ms RTT、50 ms。各法的检测是实际模型前向，其截止采用取自网络及固定阶段模型。反馈策略比较保留请求字节、等待和补包内容共同变化，不能独立归因到需求信号。历史首包未普遍留载荷摘要，配对按确定性选区、字节、时钟和新增控制记录复核。 [原统计](results/r1-marginal-abcd.json)

| 对照 | AP@0.7 差值 | 95% 场景配对置信区间 | 判读 |
| --- | ---: | --- | --- |
| B − A | +0.04262 | 见原表 | 无反馈补包有增量 |
| C − B | −0.02125 | [−0.03259, −0.00811] | 已测反馈方案欠于普通发送方对照 |
| D − B | +0.00570 | [−0.00003, +0.01148] | 未达 +0.010 阈值且区间包含零 |
| D − C | +0.02694 | [+0.01493, +0.03853] | 发送方前景信息对照优于该反馈 |

冻结正式面板上新增的 A/B/D 属于机制对照。对 B 的辅助复核只收紧模型截止至 35 ms，准确中间状态复用或补测，AP@0.7 下降 0.01794。该差值说明时间限制值得单独检验。 [35 ms 辅助表](results/r1-b-deadline35.json)

## 关键保存项

| 路线 | 原判断与边界 | 可核对材料 |
| --- | --- | --- |
| R2 发送排序 | 排除帧的改善在后续五个场景抽样未复现。全量排序扩展暂停。六帧实验用真实 CPU 检测和模型链路 | [复验原报告](results/r2-order-cpu-repeat.json) |
| R2.3 候选预筛 | 80 帧 1,045 个状态逐值验收，真实协同接收同步墙钟 P50 35.46 → 18.99 ms。同一后端比较 35 ms 逐包对未分包 AP@0.7 +0.00063，95% CI [−0.02422, +0.02208]，完整检测均为 0/80 | [无损门禁与计算时钟](results/r23-prefilter-timing.json) · [同后端配对](results/r23-incremental-control.json) · [两帧 NMS 验收](results/r23-nms-probe.json) |
| R2.4 最新状态合并 | 同 ego 的逐包版本队列，35 ms 峰值等待队列中位数 15 → 1，AP 和完整检测覆盖均未改善。50 ms 时相对逐包 FIFO 的部分状态 AP +0.01919，未增加完整检测覆盖 | [状态合并投影](results/r24-coalescing-summary.json) |
| R2.5 接收与计算流水线 | 同一包流中，把解析、搬运和散写移至尾包前。完整路径尾包后平均缩短 3.29 ms，场景配对区间约 [−3.53, −3.06] ms，35 ms 完整检测仍 0/80。去掉重复且等值粗尺度向量与索引后，应用字节中位数 239,199 → 167,021 B | [配对决策投影](results/r25-pipeline-decision.json) · [精确消息账本](results/r25-compact-wire.json) |
| R2.6 完整检测时间边界 | 去重完整状态 80/80 通过同设备逐值核验。45/50 ms 覆盖率改善支持继续研究通信和接收计算。网络到达和跨阶段排队以真实服务时长进行回放 | [配对结果](results/r26-deadline-summary.json) · [截止表](results/r26-deadline-table.csv) · [覆盖率图](results/r26-deadline-complete-rate.png) |
| 多检测任务争用 | `BLOCKED_MISSING_CONCURRENT_WORKLOAD`。现存输入缺独立任务释放时间、共享接收资源映射、共同时钟占用事件和隔离配对。EDF 未运行 | [既有诊断报告](../../archive/v2x-development/queue-diagnostic/QUEUE_DIAGNOSTIC_REPORT.md) · [阶段事件](../../archive/v2x-development/queue-diagnostic/TASK_TIMELINES.jsonl) |

## 下钻示例

1. R2.6 的 A 为收齐才计算，B 为原包流水线，C 为精确去重包流水线。每组 80 帧。在 45 ms 各完成 0/7/37，在 50 ms 各完成 16/39/60。C−B 分别 +37.50/+26.25 个百分点，逐截止点的场景配对 95% 区间 [17.50, 60.00]/[11.25, 46.25]。所有组在 35 ms 完整检测均为 0。AP 分开报告完整输出及含本地回退，不能把只在及时完成子集上的分数当作全样本 AP。 [截止表](results/r26-deadline-table.csv) · [区间及指标定义](results/r26-deadline-summary.json)
2. 有边界压力的帧 `2021_08_23_21_07_10/000097/160` 对应本地 case 1332。C 应用消息 181,156 B，包括 16 B × 17 包头、916 B 索引和 179,968 B 向量，无控制包。50 ms 下模拟完成于 50.037986 ms。尾包物化在 26.566204–26.733493 ms 等前一分片 GPU 通道。等候和占用都来自同一 ego 的同一帧，实测尾段服务事件有各自的秒表原点。 [实例投影](results/r26-frame-1332.json) · [原回执封存摘要](results/r26-completion-seal.json) · [既有代表时间线](../../archive/v2x-development/queue-diagnostic/REPRESENTATIVE_TIMELINE.md)
3. R2.6 直接比较 B/C 仍可能受不同测时批次影响。已封存的反事实控制 B 的计算服务时长，只替换成 C 的去重字节和到达时刻，45/50 ms 完成数由 7/39 到 44/64。固定 C 的计算时长，去掉序列化等待也只有 35/80 帧在 35 ms 完成。这使字节减少机制独立于测时批次，仍无法推断物理链路或多任务调度。 [共享回放总结](../../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/result_summary.md) · [共享回放原 JSON](../../archive/v2x-development/latest-opv2v/latest_run_20261126_232310/artifacts/resource-sensitivity.json)

## 核验与来源

[逐文件来源](results/SOURCES.json)区分逐字节副本与字段投影，记录归档前后的 SHA-256。实例投影的来源原件摘要与完整性封存表中的同一帧摘要相同。仓库已收录资源敏感性和队列诊断原件，分支使用已有路径。来源中的散装模型、权重、传感器数据、逐帧大表和主机环境均留在原项目，历史完整运行时项目 HEAD 缺失。对应实验的后续本地代码快照及适用范围见[本地路线沿革](notes/local-history.md)。

从含本方向的仓库根目录执行，使用 Python 3.10+ 标准库。

```bash
python3 -B research/opv2v-deadline/results/export_evidence.py
```

此命令校验 16 份证据摘要、18 个截止表单元、R1 对照符号、R2.6 实例的封存身份及包长之和。它读取已存在的结果。若同时持有原研究目录，可以传 `--source-root <path> --output <new-directory>` 重新生成同口径投影。

交接验证实测在 Ubuntu 上完成。以上只读命令通过，墙钟 0.08 s、峰值 RSS 27,284 KiB。以同脚本执行 `--source-root` 导出（输入为原项目，输出为本分支的结果目录）墙钟 0.46 s、峰值 RSS 92,100 KiB。两次都只读取归档数据，没有加载模型或执行旧确认。

2026-11-27 在 Ubuntu 和 Python 3.10.12 实际执行上述只读命令，通过全部检查。GNU `time` 测得墙钟 0.09 s、峰值 RSS 27,028 KiB、退出码 0。未加载检测模型。
