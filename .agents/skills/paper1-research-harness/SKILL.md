---
name: paper1-research-harness
description: Use the Paper 1 OPV2V and DAIR autoresearch harness to verify sealed receipts, resume authorized local checks, and prepare a single-variable research run. Use for work on this project's evidence, frozen inputs, and local handoff.
---

# 论文 1 协同感知 Harness

先读 [工作流导航](../../../research/opv2v-deadline/autoresearch/NAVIGATION.md) 选正确入口，并确认用户要做已封存证据复核、原机预检，还是已授权的实验续跑。

- **已封存证据。** 从私有仓库根运行 `python3 -B research/opv2v-deadline/autoresearch/scripts/check_shared_assets.py`。它核对可移植原件、46 帧训练例回执、R1 包时钟和导出的检测证据。结果标注为只读复核。查看 [Autoresearch README](../../../research/opv2v-deadline/autoresearch/README.md) 运行单项校验。
- **原机预检或续跑。** 先看 [本地交接](../../../research/opv2v-deadline/autoresearch/local/README.md)，核对当前输入、模型、预处理、冻结面板、代码摘要和实验授权。校验可复用回执及其全部产物后，再处理允许列表里未完成的任务。缺输入时保存阻塞原因和具体字段。GPU 资源和外部服务状态只作为运行条件。
- **新机制对照。** 用 [角色提示](../../../research/opv2v-deadline/autoresearch/protocols/PROMPTS.md) 写清单变量、基线、样本、字节范围、时钟域和停止条件。保留负结果和未执行对照。DAIR 训练例、OPV2V 模型时限回放和真实共享资源试验分别记账。多发送方或同帧两次检测都不能充当独立任务共享轨迹。

历史 supervisor 源码与服务模板用于复现记录。共享仓库的只读入口不需要设备、系统服务或数据集。当前实验判定见 [CURRENT.md](../../../research/opv2v-deadline/CURRENT.md)。
