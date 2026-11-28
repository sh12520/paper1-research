# 研究工具与方向

从这里进入共享核验工具、项目技能和跨机交接。课题状态与下一步证据要求见[当前推进](../docs/current-research.md)，历史材料按[全局目录](../docs/research-index.md)查找。

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

## 项目技能与原机入口

- 用 [`paper1-navigate`](../.agents/skills/paper1-navigate/SKILL.md) 从研究状态、证据索引下钻到具体运行。
- 用 [`paper1-research-harness`](../.agents/skills/paper1-research-harness/SKILL.md) 选择共享核验、原机预检或已有授权的续跑。统筹、执行恢复与独立复核可沿用[角色提示](opv2v-deadline/autoresearch/protocols/PROMPTS.md)。

| 方向 | 入口与运行条件 |
| --- | --- |
| RDINP | [协议、边缘执行与代理原型](../rdinp/README.md)。后续实验按 [G1-A 判定](../rdinp/experiments/durable-worker/G1A_DECISION_REPORT.md)及相应授权执行。 |
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
