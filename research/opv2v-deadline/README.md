# OPV2V 通信与接收计算时限

问题是固定感知质量和应用层通信预算后，哪些完整检测能在截止前交付，瓶颈又属于传输、同帧计算依赖还是跨任务共享。该方向保留论文 1 的协同感知开发证据，可给 RDINP 提供候选应用和强对照。当前还缺少把 OPV2V 用作 RDINP 业务验证的真实任务轨迹与 SLA。

| 想找什么 | 入口 |
| --- | --- |
| 当前判断、适用边界和下一项决定性验证 | [CURRENT.md](CURRENT.md) |
| R1 到 R2.6 的正负结果、数字和逐帧证据 | [EVIDENCE.md](EVIDENCE.md) · [历史路线](notes/local-history.md) |
| 跨机复核、冻结输入、原计算源码 | [工作导航](autoresearch/NAVIGATION.md) · [最小复现](src/README.md) · [Autoresearch](autoresearch/README.md) |
| 公开文献、两版 BlindMap 和数据来源 | [REFERENCES.md](REFERENCES.md) |
| 从全局导航出发的实际找寻与断点 | [NAVIGATION_REVIEW.md](NAVIGATION_REVIEW.md) |

仓库根目录运行 `python3 -B research/opv2v-deadline/src/check_packet_clock.py`，可核对一帧四种策略的原应用层字节与模型时间账本。标准库即可运行，无需模型、数据集或 GPU。

本机原工程为 `6g_intent_negotiation`。本目录用相对路径、版本和 SHA-256 记录原件。已共享的资源回放与争用诊断仍由 [原归档](../../archive/v2x-development/README.md) 提供。
