# PAPER1-PROBLEM-BASELINE-RESET

**RESEARCH_DIRECTION_NOT_YET_JUSTIFIED** · 2026-11-23

TFH 的可复现失败是固定业务负荷在特定降容轨迹上的 IP 截止期限退化。两个原生前传控制存在可执行入口。其中 OptimizeRBs 在 T1 的七次完结运行中守住了 VR、CG 和 AR 视频的 10 ms 门槛。现有记录既缺少可执行的应用—网络联合动作，也没有在同等观测与服务底线下证明，这些动作能解决强基线组仍留下的期限问题。建议暂缓为该方向设计新算法。

## 1. 可运行的通信场景

Windows 原生的 ns-3.42 / 5G-LENA v3.3.y 封存程序 `ns3.42-cttc-nr-fh-xr.exe` 可以模拟一个下行受限前传的小区。配置为 30 GHz、400 MHz、μ=3、PF OFDMA 和 DDDDU TDD。单 gNB 服务 12 台 UE，AR、VR、云游戏和 VoIP 各 3 台，共 18 条受计量 UDP 目的流。AR 分别产生姿态、视频和音频。AR 视频和 VR 的固定生成参数分别为 20 Mbps / 60 FPS 和 45 Mbps / 120 FPS，云游戏媒体生成参数为 30 Mbps / 60 FPS。这些参数属于仿真流量源。没有验证实际 XR 编解码、应用画面、本地 MEC、真实 RU 或物理前传。 [归档场景源码](<D:/msys2/home/16043/research/TFH02-SUBMISSION-CAMPAIGN-20261110-003718/source/contrib/nr/examples/cttc-nr-fh-xr.cc:519>) · [5G-LENA v3.3.y 发布版](https://zenodo.org/records/13929095)

五秒业务运行中，T1 容量按 `2250 → 1000 → 2250 Mbps` 变化，下探位于相对业务启动的 [2, 3) s。T2 为 `2400 → 1400 → 2400 Mbps`，下探为 [1.5, 3.5) s。两条轨迹的时间加权容量均为 2000 Mbps。恒定 C2000 匹配均值，C2250 和 C2400 用于匹配各自恢复段的当前容量。该容量是模型载入的外部条件。统计中的恢复滞后关联容量历史与控制方式，尚未识别唯一的 HARQ、RLC 或 PDCP 因果路径。 [轨迹与归档分析](TFH_ARCHIVED_EVIDENCE.md) · [归档排程实现](<D:/msys2/home/16043/research/TFH02-SUBMISSION-CAMPAIGN-20261110-003718/source/contrib/nr/examples/cttc-nr-fh-xr.cc:1877>)

## 2. 一句待验证的研究问题

在共享下行前传突然降容时，负责 VR／云游戏服务档位的应用方与控制前传调度的网络方，能否在同样的因果观测、可执行档位和前传预算下，比 `OptimizeRBs` 配合单边自适应及同动作集合的滚动对照，减少受保护流的 10 ms IP 数据报违约和恢复期中断，同时维持最低服务档与约定的 RAN 资源预算？

其中 `OptimizeRBs + 单边自适应` 和滚动对照仍待接线。10 ms 是现有数据的研究门槛。最低服务档、关键流及消耗上限须来自明确业务需求。归档无法替服务方确定这些约束。

## 3. 基线与复现状态

四种原生控制使用同一小区资源预算、拓扑和业务流，调度输入包含网络侧可用容量、已分配或待分配无线资源及所需 MCS 信息。控制方式可在启动前选择。它们共同处理前传预算约束，无单独的应用 10 ms 截止期限优化目标。2024 年 *Computer Networks* 原论文已分析受限 Open Fronthaul 下 XR／CG 的吞吐与时延。2025 年 NFV-SDN 论文给出了四种机制、调度阶段与不同业务吞吐、时延的实证对照。 [Koutlia 与 Lagén 2024](https://doi.org/10.1016/j.comnet.2024.110722) · [NFV-SDN 2025](https://doi.org/10.1109/NFV-SDN66355.2025.11349441) · [调度接口源码](https://gitlab.com/cttc-lena/nr/-/raw/5g-lena-v3.3.y/model/nr-fh-control.cc)

| 基线 | 决策输入与可执行动作 | 目标 | 源码与复现难度 |
|---|---|---|---|
| Dropping | 调度后检查前传剩余预算，PHY 丢弃超预算的 DCI／数据分配 | 快速限制当槽前传分配 | 有官方源码和历史 BASE04 运行记录。启动参数可选。TFH02 无完整同设计配对，未给出同组期限比较。 |
| Postponing | 调度后检查前传预算，在 MAC 取消不合适的分配，RLC 保留待发数据 | 服从当前预算并延迟发送 | 有官方源码，TFH02 T1 10 次完成。复用历史启动参数和流量源。 |
| OptimizeMcs | 调度分配后按剩余预算限 MCS，必要时推迟发送 | 通过调制压缩和延期限制前传负载 | 有官方源码和历史执行文件。本轮与 OptimizeRBs 成对复跑。 |
| OptimizeRBs | 分配时按剩余前传预算约束可分配 RB，必要时推迟发送 | 在分配阶段限制前传负载 | 有官方源码和历史执行文件。本轮与 OptimizeMcs 成对复跑。既有 TFH02 三次 T1 PDCP 路径异常须单列。 |
| 固定业务档 | 启动前固定媒体生成码率、FPS；运行中不决策 | 保持同一名义服务配置 | 历史驱动已执行单一固定负荷。另一固定档须修改驱动配置接口或构建参数后验证实际发包，不能称已比较多个质量档。 [XR 业务模型](https://doi.org/10.1109/JSAC.2023.3273701) |
| 简单业务降级 | 过去接收反馈窗口触发码率／FPS 降档与恢复 | 在可接受的最低档约束下适应丢包或明确的超期观测 | XR Loopback 原论文与生成器实现可用。v3.3.y 无生产调用点，须接收端采样、反馈、动作调用和应用生效事件。 [原论文](https://doi.org/10.1109/JSAC.2023.3273701) · [官方生成器](https://gitlab.com/cttc-lena/nr/-/raw/5g-lena-v3.3.y/utils/traffic-generators/model/traffic-generator-3gpp-generic-video.cc) |
| 预定义菜单协商 | 相同公开状态下从固定档位菜单给出提案，应用和网络分别核对底线 | 在双方接受的档位中完成选择，必要时回退 | Sharma 等的原型已包含资源感知替代项和接受／拒绝。配套可运行源码未核实。OpenSlice 平台有公开实现，未核实相同 TFH 负荷的联动复现。两者均需本地适配。 [Sharma 等 2023](https://doi.org/10.1109/MCOM.001.2200504) · [OpenSlice](https://osl.etsi.org/documentation/latest/architecture/ai/) |
| 滚动时域优化 | 过去容量、交付和队列观测形成短期预测，滚动选择第一步公开可执行档位 | 在同样底线下最小化期限违约和中断，受切换与资源约束 | Yin 等的原方案对视频播放缓冲、吞吐与分片码率优化。有公开 RobustMPC 实现，不能直接控制 TFH 的 UDP 媒体源。本场景没有已运行版本。 [MPC 论文](https://doi.org/10.1145/2785956.2787486) · [公开实现](https://github.com/hongzimao/pensieve/blob/master/rl_server/robust_mpc_server.py) |

OptimizeMcs 与 OptimizeRBs 是两条已执行的较强**网络侧**基线。它们的共同动作范围是原生前传控制下的调度，任何上线的应用降档或预约都会改变可执行动作范围，须另设同动作、同观测的对照。已发表意图框架在下文并列审查，未核验可运行版本的工作只用作先例和基线设计来源。

## 4. 执行接口、公平性与指标

| 项目 | 已验证接口或口径 | 当前边界 |
|---|---|---|
| 前传配置 | `--fhCapacity`、`--fhControlMethod`、`--ohDyn`。历史 driver 以 `SetCellFhCapacity` 排入容量变化事件；容量由同小区活动 BWP 共享，单位 Mbps。 | 控制器不读取未来轨迹。可通过启动固定控制类型，尚无运行中安全切换类型的验证。容量数值由场景统一施加，基线不能自行增容。 |
| 业务动作 | 生成器的 `DataRate`、`Fps` 在初始化前设置。视频 `ReceiveLoopbackInformation` 可更新生成过程及缓存分布。 | 当前 driver 未接该回调。单独改运行中属性不足以可靠改变缓存的生成分布。档位切换、进入／退出时刻、实际生效回执、接收反馈和协商均需最小驱动接线及验证。没有计算卸载或真实编解码执行接口。 |
| IP 数据报违约 | 用流标识与数据报编号关联源首发和目的端完整重组接收。按源端发送时间分窗，`迟到 + 截止观测还未完整接收` 除以源唯一数据报数。10 ms 恰好及时。 | 分列迟到与未观测接收。后者不足以定位物理丢包。应用主动降档时，应同时记录名义和实际码率／FPS及固定业务需求下的及时数据报计数，避免减少分母造成表面改善。 |
| 关键业务可用性与中断 | 分 AR 姿态／视频／音频、VR、CG、VoIP 计数。按 100 ms 源端非空窗口统计零及时交付；恢复相对同法当前高容量，使用连续三个窗口及时率绝对差均小于 5 pp。 | 这些是 IP 层指标。会话／画面可用性、帧完成率和交互卡顿待实现。当前关键业务与各自底线尚无外部业务证据。 |
| 资源成本 | `RequiredFhDlThroughput` 为模型请求前传速率；`UsedAirRbs` 为模拟空口用量。可报告整次 FH 等效 Mbit、非零时隙 p95 Mbps 和空口 RB 记录值之和。 | 归档资源 trace 未保留时隙时戳，不能自称有分相位成本；未测以太网线速字节、货币成本、RAN 能耗或应用计算。 |
| 协商 | 无对应 TFH 运行日志。 | 只能标为待实现。未来须记录每次协商的提出、接受、拒绝、应用生效与回退，才可报告周期达成率、轮次及生效延迟。 |

历史两种控制器的公平对照使用同一序号、容量时间表、拓扑与源端业务，动作差异仅来自调度控制。将来比较业务档位策略时，所有方法须使用相同的预先声明档位、改变档位的生效延迟、观测时标、预测输入、应用底线和故障处理。原生 FH 模式应固定为同一个，或向所有策略提供同一已验证的模式选择动作。发布容量轨迹仅用于场景复现，任何有决策的对照均从当前及过去观测估计，避免未来轨迹泄露。 [逐数据报口径与重算脚本](TFH_ARCHIVED_EVIDENCE.md) · [资源 trace 接口](<D:/msys2/home/16043/research/TFH-MECH-01-20261111-224343/evidence/source/contrib/nr/model/nr-fh-control.cc:51>)

## 5. 业务失败与剩余困难

**本次成对复跑。** 两种原生控制复用了归档 T1 的同一既有 RngRun=7，且都正常退出。两次的拓扑、容量事件和源端 IP 数据报序列摘要完全相同。分别对各自归档运行比较，`uePositions.txt`、`capacity-events.csv` 和 `packet-events.csv` 均逐字节一致。早先尝试的一秒业务时长被冻结驱动的五秒参数检查拒绝，未产生可比较的网络结果。本对照使用未修改的历史参数和原二进制。 [OptimizeMcs 运行凭据](native_replay/OptimizeMcs/receipt.json) · [OptimizeRBs 运行凭据](native_replay/OptimizeRBs/receipt.json) · [执行脚本](run_native_smoke.py)

| 复跑的 T1 源时间窗口 | OptimizeMcs VR／CG 违约数 | OptimizeRBs VR／CG 违约数 |
|---|---:|---:|
| 下探期 | 354／356 · 179／179 | 0／356 · 0／179 |
| 恢复首秒 | 225／359 · 84／180 | 0／359 · 0／180 |

复跑中的所有上述违约记录均为最终接收但超过 10 ms。此对照重复了一个既有序号，未增加独立场景数。从项目根目录运行 `py -3.11 -B PAPER1-PROBLEM-BASELINE-RESET/run_native_smoke.py` 可复现；脚本拒绝覆盖已有运行目录，复跑应使用新副本中的空输出目录。

**历史样本扩展。**

| T1 低容量段 | 完成数 | VR／CG／AR 视频违约率中位数 | 已知执行失败 |
|---|---:|---|---:|
| OptimizeMcs | 10 | 99.861%／100%／78.440% | 0 |
| Postponing | 10 | 69.137%／47.633%／25.348% | 0 |
| OptimizeRBs | 7 | 0%／0%／0% | 3 |

OptimizeMcs 的下探期 VR 有 3,592／3,605 个迟到，CG 有 1,797／1,797 个迟到，两类全部最终接收。两类整次接收 IP 字节与同法 C2000 对照在 10／10 对中相同。恢复首秒相对同法恒定 C2250 的中位违约差为 VR **+47.654 pp**、CG **+31.111 pp**，恢复阈值的时间中位数为 **0.55 s／0.40 s**。T2 的同类现象未出现在 OptimizeMcs 的归档低容量和恢复首秒中。结果支持“同均值可掩盖期限差异”，也表明失约依赖波形与控制方式。  [归档证据、分箱与配对](TFH_ARCHIVED_EVIDENCE.md)

对 T1 两者共同完结的七个运行，Postponing 相对 OptimizeRBs 的整次模型前传负载中位配对差为 −81.315 Mbit，空口 RB 记录值之和差 −32,509；对应下探期 VR／CG 违约差为 +68.611／+47.222 pp。这是可观测的资源／服务折衷。现有数据没有证明这些额外资源碰到了业务方的实际成本上限。OptimizeRBs 的三次 PDCP 路径退出只限制结论覆盖范围，不得计作实际丢包或应用中断。现有同动作基线的残余期限失败尚未证实。 [逐运行对照](tfh_archived_method_pairs.csv)

## 6. 文献先例与可检验的潜在差别

- **意图替代、用户接受。** Sharma、Bhamare、Kassler、Taheri 的 2023 *Intent Negotiation Framework for Intent-driven Service Management* 已由网络生成满足底层物理或虚拟资源的替代项，交意图发起者接受或拒绝。Java／SFC 原型支持流程思想，尚未核实其公开实现能复现这里的前传容量观测、运行中媒体调档和 IP 数据报期限闭环。 [出版记录](https://doi.org/10.1109/MCOM.001.2200504) · [作者预印本](https://doi.org/10.36227/techrxiv.20490093.v1)
- **智能体与可执行 SLO。** Tranoris 与 Trantzas 2026 年的 OpenSlice 研究通过目录、约束、SLO／SLA 和费用选项进行用户共创，确认后映射为执行动作并使用测试核验。计划面协商、能力感知和部署核验是明确先例。潜在差别须落实到运行中前传变化与受保护媒体流的时标和动作。 [ITU 原文](https://doi.org/10.52953/FPSZ2168) · [ETSI OpenSlice 模块](https://osl.etsi.org/documentation/latest/architecture/ai/)
- **动态确定性跨域合同。** Christodoulopoulos 与 Selentis-Boulntadakis 的 2026 arXiv v2 用流量声明、提前量、网络演算与仿真筛选上行共享 TDM-PON 的安全 grant 切换，给出 100 μs 级期限例证，也覆盖静态 5G–TSN。已公开的原文足以否定“动态可执行跨域合同尚无人研究”的表述。论文所列仿真 fork 的可运行性未核实。这里可检验的差别是下行媒体档和保护 IP 流的策略问题。 [原文](https://arxiv.org/html/2608.09312v2)
- **前传、切片与 XR 期限策略。** O-RAN 规范已经考虑共享前传的带宽波动与 O-DU 调度输入，3GPP 已定义应用响应 RAN 提供码率建议。XR Loopback 已执行媒体码率／FPS 调整。Casparsen 等已实现近实时 VR PRB 切片，QCON 已在 O-RAN 中施行 QoE 感知的多连接调度。调整资源或媒体质量本身很难构成差别。 [O-RAN 附录 L.6](https://www.etsi.org/deliver/etsi_ts/103800_103899/103859/12.00.01_60/ts_103859v120001p.pdf) · [3GPP §5.3](https://www.etsi.org/deliver/etsi_ts/126500_126599/126506/18.02.00_60/ts_126506v180200p.pdf) · [XR Loopback](https://doi.org/10.1109/JSAC.2023.3273701) · [VR 切片](https://doi.org/10.1109/OJCOMS.2025.3571498) · [QCON](https://www.usenix.org/conference/nsdi26/presentation/lee)
- **直接挑战基线。** WCNC 的 AdjustRBs 已研究利用 RB 调整减轻前传约束，XR PDU-set 感知调度也已有方法。前者与历史 `OptimizeRBs` 的动作关系须按代码核验；后者以 PDU 集为单位，复用本数据报级指标前须建立映射。外部材料未纳入本轮执行统计。 [AdjustRBs](https://doi.org/10.1109/WCNC61545.2025.10978658) · [作者软件存档](https://zenodo.org/records/17091326) · [PDU-set 调度](https://doi.org/10.1109/TNSM.2025.3631520)

只有在独立应用方与网络方确实各自控制对方不能替代的执行动作和底线，且同样有权执行动作的有力单边或滚动策略仍反复出问题时，才值得检验基于降容和恢复窗口的双边期限承诺。测试应以约定动作实际生效、受保护数据报期限、服务底线及资源消耗衡量差别。现有证据不足以主张存在该差别。

## 7. 决定

暂停新方法研究。TFH 已有可复现的 IP 期限问题，但目前可见的失败主要落在较弱的网络控制配置上。要重新判断该方向，最小的证据缺口是把一个已有应用反馈降档执行接口接到冻结场景，固定可观测底线，使用同一网络强基线对照固定档与因果降档。如果既有控制已满足底线，或无法证明应用方和网络方联合承诺的执行需要，应停止该路线。此项属于将来验证，未在本轮修改模拟器。

独立的 GENSPACE 冻结候选校验覆盖 148 个研究源文件、75 项资产及绑定的执行基础设施。原研究授权仍为 `METHOD_HOLDOUT=false` 和 `CONFIRM=false`，未启动原独立确认。报告、归档重算和两条 TFH 复跑仅写入本轮目录。 [只读绑定校验](frozen_research_binding_check.json)
