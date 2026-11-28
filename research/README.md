# 研究工具与方向

从这里进入共享核验工具、项目技能和跨机交接。课题状态与下一步证据要求见[当前推进](../docs/current-research.md)，历史材料按[全局目录](../docs/research-index.md)查找。

## 工具来源与可用范围

| 资产 | 来源 | 复用内容与入口 | 使用边界 |
| --- | --- | --- | --- |
| ResearchGate5 工作包与一键交接包 | 本机保留的五阶段工作包、2026-11-14 Auto Codex 交接包 | 五阶段包供参考阶段检查和反方审阅，交接包用于核对当时的门禁、证据和缺件。原件在本机 `论文1/本地资料/历史交接/ResearchGate5/`。 | 历史模板及状态快照。现行 RDINP 阶段与执行授权按 [GOAL](../docs/proposals/GOAL.md) 和[当前推进](../docs/current-research.md)判断。 |
| `agents_final_tech` 同伴项目 | OPV2V 工作流记录的封存版本 `e70b222` | 借鉴多层分工、检查点、独立复核和失败归档，见[工作流的来源和判断](opv2v-deadline/autoresearch/WORKFLOW.md#工作流的来源和判断)及[角色提示](opv2v-deadline/autoresearch/protocols/PROMPTS.md)。 | 借鉴流程。原启动器与个人配置随原归档保存。 |
| OPV2V／DAIR 原机 AutoResearch | 第二台电脑 Agent 的实际运行与交接 | 查阶段调度、GPU 预检、逐帧续跑、封存回执及 systemd 示例。 [原机交接](opv2v-deadline/autoresearch/local/README.md) · [执行与归档](opv2v-deadline/autoresearch/WORKFLOW.md) | 完整推理与续跑依赖原机 Linux、模型、数据、原始回执和现行授权。 |
| 跨平台共享 Harness | 从远端 Harness 提炼的任务登记、输入摘要、任务锁和回执机制 | 用本页下方的 `list`、`check` 及回执命令。在 Windows 与 Ubuntu 实测通过两项任务的核验、回执和复用。 | 当前登记 OPV2V／DAIR 封存证据及 RDINP G1-A 导出核验。新实验用各方向的执行器和对应授权。 |
| 仓库 Skills | 远端 Agent 交接，合入后补上跨平台入口 | [`paper1-navigate`](../.agents/skills/paper1-navigate/SKILL.md) 定位状态与证据，[`paper1-research-harness`](../.agents/skills/paper1-research-harness/SKILL.md) 指引核验、预检及已授权续跑。 | 作为项目内的 Agent 操作指南，实际执行按任务清单和当前授权。 |

## 共享核验入口

在仓库根目录使用 Python 3.10 或更高版本。Windows PowerShell 和 Linux 可运行同一套命令。如果解释器命令为 `python3`，用它替换 `python`。

```sh
python -B research/harness.py list
python -B research/harness.py check opv2v-evidence
python -B research/harness.py check rdinp-g1a-evidence
```

| 任务 | 核验范围 |
| --- | --- |
| `opv2v-evidence` | OPV2V 共享包时序和结果表、DAIR 训练示例封存回执 |
| `rdinp-g1a-evidence` | RDINP G1-A 已存档的配对计划与逐任务导出 |

`check` 读取原件并输出核验结果。需要在本机保留输入摘要和回执时，改用 `run`。用回执目录名替换示例的 `ATTEMPT_ID`。

```sh
python -B research/harness.py run opv2v-evidence
python -B research/harness.py verify opv2v-evidence --attempt ATTEMPT_ID
```

回执默认位于 `runs/research-harness/`。如需自定义位置，在动作前传 `--state-dir DIR`，复核时使用相同目录。`run` 优先复用输入身份相同且摘要有效的成功回执。`recover TASK` 在任务锁内登记已中断且留有预约记录的尝试。共享入口的任务清单由[执行脚本](harness.py)维护。

使用本地文件系统保存回执。回执绑定输入摘要、Python 版本和平台，发布时保留已有文件。`verify` 给出记录状态和摘要核验结果，完整事件链和科研结论仍以各研究方向的原始记录为依据。

## 各方向的原机入口

| 方向 | 入口与运行条件 |
| --- | --- |
| RDINP | [协议、边缘执行与代理原型](../rdinp/README.md)。现行状态见[当前推进](../docs/current-research.md)。[G1-A](../rdinp/experiments/durable-worker/G1A_DECISION_REPORT.md)用于复核已封存证据。 |
| CS-ODS | [合同搜索代码与小型测试](../csods/README.md)。需要全量实验资料时按[证据索引](../docs/evidence-index.md)定位。 |
| OPV2V／DAIR | [车路协同方向](opv2v-deadline/README.md)内保存 R1–R2.6 开发证据。Linux 原机执行涉及固定模型、数据和逐帧回执，详见[原机交接](opv2v-deadline/autoresearch/local/README.md)。 |

## 增加研究方向

在同一仓库的 `research/<方向短名>/` 记录新方向，需要独立协作时使用对应分支。下面的文件可按研究内容调整。

- `README.md` 说明问题、当前结果和运行入口。
- `CURRENT.md` 和 `EVIDENCE.md` 记录阶段、假设、研究判断和可追溯的正负证据。
- `REFERENCES.md` 优先复用[共享书目](../literature/README.md)的键和 DOI。
- `autoresearch/` 或现有工作流目录保留可共享的提示词、实验脚本、评估条件和小型复现。旁支线索可单独留存。

接入共享核验时，保留研究代码和证据原路径，编写一个以退出码表示核验结果的只读脚本，然后在 [任务清单](harness.py)登记任务名、核验脚本和证据输入。新任务由共用入口运行，自动获得输入记录、锁和可复核回执。需要 GPU、采集新数据或持出确认的运行仍按对应方向的授权和执行条件接续。

跨机整理、上传和验收见[第二台电脑的 Codex 提示词](../docs/collaboration/SECOND_COMPUTER_AGENT_PROMPT.md)。此前的证据验收和范围见[OPV2V 接入审查](../docs/collaboration/OPV2V_INTEGRATION_REVIEW.md)。
