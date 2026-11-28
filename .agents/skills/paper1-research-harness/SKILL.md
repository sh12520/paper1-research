---
name: paper1-research-harness
description: Use the Paper 1 research harness to verify shared RDINP and OPV2V evidence, record checks on Windows or Linux, or resume authorized OPV2V and DAIR tasks on the original host.
---

# 论文 1 研究 Harness

从 [研究工具入口](../../../research/README.md) 查已登记任务。先确认用户要做共享证据复核、本机留痕，还是原机预检与已授权续跑。

- **共享证据。** 在仓库根运行 `python -B research/harness.py list`，再对任务使用 `check`。Windows 与 Linux 共用该入口。需要写本机回执时使用 `run`，后续按尝试 ID `verify`。RDINP 检查只覆盖已导出的计划和任务表。OPV2V 检查包含 46 帧 DAIR 训练例的封存回执与模型时钟。两者各自保留证据边界。
- **原机预检或续跑。** 先看 [本地交接](../../../research/opv2v-deadline/autoresearch/local/README.md)，核对当前输入、模型、预处理、冻结面板、代码摘要和实验授权。校验可复用回执及其全部产物后，再处理允许列表里未完成的任务。缺输入时保存阻塞原因和具体字段。GPU 资源和外部服务状态只作为运行条件。
- **新机制对照。** 用 [角色提示](../../../research/opv2v-deadline/autoresearch/protocols/PROMPTS.md) 写清单变量、基线、样本、字节范围、时钟域和停止条件。保留负结果和未执行对照。DAIR 训练例、OPV2V 模型时限回放和真实共享资源试验分别记账。多发送方或同帧两次检测都不能充当独立任务共享轨迹。

历史 supervisor 源码与服务模板用于复现记录。共享仓库的只读入口不需要设备、系统服务或数据集。当前实验判定见 [CURRENT.md](../../../research/opv2v-deadline/CURRENT.md)。
