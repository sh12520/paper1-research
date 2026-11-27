# TFH 归档证据重算

## 样本与指标

取历史 TFH02 单小区混合 XR 配置。每种 AR、VR、云游戏（CG）和 VoIP 各有 3 台 UE，采用 30 GHz、400 MHz、PF 调度及 DDDDU。应用在模拟时间 0.4 s 启动，成功运行在 5.41 s 停止。以下相位使用相对应用启动的时间。T1 用 2,250→1,000→2,250 Mbps，低容量在 [2,3) s。T2 用 2,400→1,400→2,400 Mbps，低容量在 [1.5,3.5) s。两者的五秒容量均值均为 2,000 Mbps，与恒定 C2000 对照一致。恢复历史使用同一控制方法的恒定高容量 C2250 或 C2400。 [归档配置与数据目录](<D:/msys2/home/16043/research/TFH03R3-PRESUBMISSION-20261110-150106/data>) · [原 TFH02 预注册](<D:/msys2/home/16043/research/TFH02-SUBMISSION-CAMPAIGN-20261110-003718/evidence/PREREGISTRATION.md>)

截止期限为研究设定的 10 ms IP 层门槛。以源端首个 IP TX 至目的端完整 IP RX 计时，恰好达到门槛算及时。按源端首发时间划分相位，将最终完成接收但超时与观测截止时仍无完整 RX 分开记录。率的分母是各源时间队列的唯一已生成 IP datagrams，分子为迟到与未观测完成之和。该定义可复算 IP 层可用性代理，无法由此推出游戏画面、XR 帧或应用会话的可用性。 [Datagram 重建范围](<D:/msys2/home/16043/research/OJCOMS-SUBMISSION-MECH-FINAL-20261112-113922/artifact/data/DATAGRAM_RECONSTRUCTION_SCOPE.md>)

归档共 130 个计划运行，125 个完成，5 个 PDCP 路径执行失败。T1 的 OptimizeRBs 在 RngRun 11、13、15 失败。T2 的 OptimizeRBs 在 RngRun 7 失败，Postponing 在 RngRun 10 失败。未用替补。按相同 RngRun 和流量类别计算配对差，控制器间只使用双方均完成的交集。T1 交集中的相同流量源发出计数一致，具体索引及布尔检查在 CSV 中。失败可能与处理过程有关。以下给出成功运行条件下的描述性中位数与实测范围。数据不足以支持将缺失视为独立、计算可推广的区间或为执行失败评定 QoS。 [归档运行清单](<D:/msys2/home/16043/research/TFH03R3-PRESUBMISSION-20261110-150106/data/TFH02_RUN_MANIFEST.csv>) · [逐运行配对](tfh_archived_method_pairs.csv)

## T1 容量下探的违约与恢复

| 原生前传控制 | 完成配对数 | LOW 违约中位数 VR / CG / AR 视频 | LOW 相对 C2000 的配对违约差中位数 VR / CG | LOW 未观测完整接收 VR / CG / AR 视频 |
|---|---:|---:|---:|---:|
| OptimizeMcs | 10 | 99.861% / 100% / 78.440% | +99.861 / +100 pp | 0 / 0 / 0 |
| Postponing | 10 | 69.137% / 47.633% / 25.348% | +66.342 / +45.833 pp | 1 / 0 / 0 |
| OptimizeRBs | 7 | 0% / 0% / 0% | 0 / 0 pp | 0 / 0 / 0 |

OptimizeMcs 在 T1 低容量时的 VR 是 3,605 个中有 3,592 个超时，CG 是 1,797 个中全部超时。这些 datagrams 最终均收到。同法的 T1 和 C2000 在这两类流量的整次运行中，各有 10/10 对的接收 IP 字节完全相等。OptimizeRBs 的七次完成运行共发送 2,530 个 VR、1,260 个 CG 及 1,259 个 AR 视频低容量期 datagrams，全部及时。T2 中 OptimizeMcs 的这三类流量在下探期和恢复第一秒均无违约，表明 T1 现象不能外推到任意同均值波动轨迹。 [队列计数与配对](tfh_archived_cohorts.csv)

独立从冻结的 OptimizeMcs 逐 datagram 文件按 100 ms 重新分箱。T1 低容量期，CG 在 10 次运行的每次 10 个非空窗口都没有及时交付，VR 每次有 9–10 个这样的窗口。恢复首秒，零及时交付窗的中位数为 VR 4 个和 CG 2.5 个。同期 T1 相对 C2250 的配对违约差中位数为 VR +47.654 pp 和 CG +31.111 pp。TFH 的恢复阈值要求连续三个完整 100 ms 窗口中，及时率与高容量对照的绝对差均小于 5 pp，归档观察到 VR 恢复中位数 0.55 s（0.40–0.70 s），CG 为 0.40 s（0.30–0.50 s）。OptimizeRBs 的七个匹配完成运行均为 0 s。Postponing 缺少恒定高容量匹配运行，无法用这一定义比较恢复时间。该观察描述 IP 层期限服务中断及恢复，无法判断物理链路是否断开。 [100 ms 窗口重算](tfh_archived_ip_bins.csv) · [归档恢复时间](<D:/msys2/home/16043/research/TFH03R3-PRESUBMISSION-20261110-150106/data/TFH02_DEADLINE_RECOVERY_TIME.csv>)

T1 下探期，OptimizeMcs 的 AR pose、AR audio、VoIP 违约率中位数为 12.4%、12.6%、0%。这些流量可分别测量，同时没有记录证明哪个应用流应享有独立最低服务要求或可以在会话内调档。所有档位声明须建立明确的业务动作与服务约束。 [按流量重新分箱的汇总](TFH_ARCHIVED_METRICS.json)

## 原生控制策略间的资源差异

T1 七个同时完成的 RngRun 为 7、8、9、10、12、14、16。以 Postponing 减 OptimizeRBs，低容量期配对违约差中位数为 VR +68.611 pp、CG +47.222 pp。整次运行的模型 FH 等效负载中位配对差为 −81.315 Mbit，空口 RB 记录值之和为 −32,509，非零 FH 时隙速率的 p95 为 −166.992 Mbps。这三个成本指标使用整次运行的记录时隙，包括启动前及尾段，且没有时隙时间戳支持分阶段成本。FH 等效量是时隙模型速率按 125 µs 转换后的和，未测量以太网线速字节、部署能耗或应用计算成本。OptimizeRBs 减 OptimizeMcs 的 FH 等效量中位配对差为 −729.743 Mbit，而非零时隙速率 p95 增加 424.320 Mbps。不同资源指标可有不同方向，归档并未建立总体成本最优性。 [逐运行资源配对](tfh_archived_method_pairs.csv) · [原始时隙资源汇总](<D:/msys2/home/16043/research/TFH03R3-PRESUBMISSION-20261110-150106/data/TFH02_RESOURCE_SHAPING_FINAL.csv>)

## 本次证据能支持的判断

历史对照已证实特定波动轨迹中的真实仿真 IP 截止期限退化、吞吐掩盖以及恢复历史。现有资产同时显示，OptimizeRBs 在完整的 T1 运行中没有观察到同类违约。运行不完整限制了对其稳健性的判断。可作为待验证问题的是，给定相同因果观测及既定网络成本和业务最低档位，应用与网络的联合调整能否改善两个提供同样调整动作的基线。归档没有这样的运行，也没有可核验的协议达成率、轮次或协商延迟。因此，单靠这些数据无法建立新增协商研究问题。

## 复现

在项目根目录运行 `py -3.11 PAPER1-PROBLEM-BASELINE-RESET/derive_tfh_archive_evidence.py`。脚本仅使用 Python 标准库，核对完成状态、配对索引、唯一 datagram 及可比源队列计数，重新分箱结果逐运行与归档 LOW、RECOVERY-1 计数核对。结果与输入 SHA-256 写入本目录。脚本不会运行模拟或生成研究种子。
