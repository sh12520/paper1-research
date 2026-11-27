# 文献、模型版本和数据

已共享键沿用 [核心书目](../../literature/references.bib) 和 [文献导航](../../literature/README.md)。方向新增条目在 [references-extra.bib](references-extra.bib)，按 DOI 和 arXiv 识别。公开原文可由链接取得。以下引用用于限定实验解释。

| 引用键 | 与本方向的关系 |
| --- | --- |
| `xu2022opv2v` | 仿真 V2V 数据与融合评测来源。默认城镇与 Culver City 分开处理，帧号是传感器索引。 [OPV2V 原文](https://arxiv.org/abs/2109.07644) · [数据划分](https://opencood.readthedocs.io/en/latest/md_files/data_intro.html) |
| `yu2022dairv2x` | 实采 V2I 协同检测及官方划分。验证需要车辆和路侧配对点云、标注与标定。 [CVPR 原文](https://openaccess.thecvf.com/content/CVPR2022/html/Yu_DAIR-V2X_A_Large-Scale_Dataset_for_Vehicle-Infrastructure_Cooperative_3D_Object_Detection_CVPR_2022_paper.html) · [数据入口](https://github.com/AIR-THU/DAIR-V2X#dataset-download) |
| `zhu2026blindmap` | INFOCOM 2026 会版，DOI `10.1109/INFOCOM59046.2026.11571528`，源代码独立登记。历史会版权重匹配和本文时延分解仍缺可复核结果。 [共享记录](../../literature/README.md) · [会版源码](https://github.com/AlexZhu2000/BlindMap) |
| `zhu2026deadline` | 后续 receiver-conditioned 实现。开发实验固定 TMC commit `075b2c7120277a619f41bc49a58e3905ffad7aa7` 及全 LiDAR OPV2V epoch 37。作者发布仓库及 checkpoint 是复现入口。 [TMC 源](https://github.com/NUAA-SmartSensing/BlindMap) · [固定发布说明](https://huggingface.co/Davinsteinsudas/BlindMap/blob/c669cfff914cfc38320b475331c84e80d5e41955/README.md) |
| `hu2022where2comm` · `yang2023how2comm` | 空间置信度选择与通信路径的基线文献。共享骨干请求对照有自己的实验定义，官方 Where2comm 原生匹配权重结果仍缺。 [Where2comm 论文](https://papers.neurips.cc/paper_files/paper/2022/hash/1f5c5cd01b864d53cc5fa0a3472e152e-Abstract-Conference.html) · [How2comm 论文](https://proceedings.neurips.cc/paper_files/paper/2023/hash/4f31327e046913c7238d5b671f5d820e-Abstract.html) |
| `xu2025cosdh` | §3.3 和表 2 区分供给、需求及晚融合。需求掩码消融从 1.99 降至 1.82 Mbps，AP@0.7 从 92.62% 到 92.60%。已有单轮需求交换先例，附录的计算时间和通信估计缺少按真实应用截止采用的逐任务账本。 [CVPR 版](https://openaccess.thecvf.com/content/CVPR2025/html/Xu_CoSDH_Communication-Efficient_Collaborative_Perception_via_Supply-Demand_Awareness_and_Intermediate-Late_Hybridization_CVPR_2025_paper.html) · [表 2 HTML](https://arxiv.org/html/2503.03430v1) |
| `yan2026sec` | 预印本 §3.2 和表 3 的供需乘积门控对比供给单侧，OPV2V 逐帧 AP@0.7 为 0.8068→0.8081。64 KiB 按协作者特征负载计，使用逐帧 AP；控制报文时序与按期回退另需核对。 [arXiv v1 全文](https://arxiv.org/html/2611.22439v1) |
| `lee2024causality` | 真实车间通信的请求响应链路调度可作为探索时延分布的出处。它不提供本地接收端的独立检测任务争用证据。 [原文](https://doi.org/10.3390/s24227142) |

本地方向的差异焦点是应用层全字节、发送与接收计算的因果时间以及按期可采纳的检测输出。以上 CoSDH、SEC 是原文核读，未用本项目冻结条件再运行。原本地核读路径为 `papers/related-work/SEC_COSDH_COMPARISON.md`，全文下载、访问令牌和个人书目库留在原设备。
