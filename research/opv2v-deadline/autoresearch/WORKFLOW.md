# 执行与归档

## 实际运行过的工作流

- 早期预检和证据审计由 [允许列表](scripts/research_harness_tasks.py) 驱动。输入、输出各作哈希，锁内发布单次追加预约与终态回执，缺件保留为阻塞。DAIR 预检和 GPU 预检各自独立终结。46 帧训练示例的审计在原机重调用已验证成功回执。
- OPV2V 冻结日程的正式阶段按本地逐帧回执推进。覆盖检查以 `scene × timestamp × receiver × strategy × budget` 明确统计，不同策略的同帧可用性分列。检查点复用绑定模型、冻结规则、首包和序列化后的字节计量。曾暂停未达门槛的全量排序，保留 273 帧完成回执。R2.6 用 R2.5 原路径与流水线的既有 80 帧 CUDA 回执，只补做去重路径实测并查等价。监督器随后登记主报告与单因素资源敏感性回放为完成。该回放每次只改变一个链路或服务参数。
- 原机使用 Ubuntu 用户级 systemd 每五分钟调用一次监督器，由应用锁和瞬态 worker 避免重复启动。续跑现场以实际剩余 GPU 资源、冻结输入和签封完成回执为依据。R2.6 的 [监督回执字段摘录](archive/receipts/opv2v-r26-supervisor-extract.json) 包括 CUDA 小样本验收、冻结面板派发、CPU 资源敏感性派发和 `r26_complete`。这份摘录保留原文件相对路径及 SHA-256，完整源回执留本地。
- 文献索引曾用 Undermind 发现 88 条候选，在原文与公开来源核验后保留 9 篇题名匹配且 SHA-256 已登记的公开 PDF。原机 Zotero Desktop 服务当时未连通。协作目录的原选择器与 [公开候选表](archive/source/related-work.json) 记录如何配合公开 PDF 地址和预印本编号；PDF 与会话记录在本机保留。 [共享文献入口](../../../literature/README.md)

## 源码入口及依赖

| 原工程入口 | 职责 | 协作定位 |
| --- | --- | --- |
| `scripts/research_harness.py` 和 `scripts/research_harness_tasks.py` | 本地允许任务、输入身份、原子预约与终态、复用、恢复 | [运行命令与实测](README.md)，代码按原相对布局保存 |
| `scripts/autoresearch_opv2v.py` | `supervise()` 评估阶段及资源，`advance_r26()` 消费 prior CUDA 回执，`enqueue()` 派发阶段 worker | [留档源码](archive/source/autoresearch_opv2v.py.txt) |
| `scripts/opv2v_autoresearch_coverage.py` | 完整核对正式、探索性、归档复用三类覆盖，检查同首包与序列化字节 | [留档源码](archive/source/opv2v_autoresearch_coverage.py.txt)。依赖冻结面板、`audit_opv2v_budgets.py`、`opv2v_network.py`、同首包检查器和原逐帧回执 |
| `scripts/run_opv2v_formal.py` 与 `scripts/run_opv2v_feedback_control.py` | R1 固定面板推理和同首包控制 | 原工程保留完整模型环境、配置和序列化证据 |
| `scripts/run_opv2v_r26.py` 与 `scripts/opv2v_r25_pipeline.py` | R2.6 实际 CUDA 接收、融合、检测与 CPU 后处理 | CUDA 推理入口一帧一帧执行，不支持由该入口复现独立任务争用 |
| `scripts/report_opv2v_r26.py` 与 `scripts/report_opv2v_r26_resources.py` | R2.6 完成时钟、场景配对和单因素资源分析 | 输出使用真实阶段耗时与冻结链路模型。该模型回放没有物理链路实测 |
| `scripts/zotero_related_work.py` | 依照题名、DOI、PDF 版本与哈希复核候选；可选调用机器上的 Zotero 本地接口 | [留档源码](archive/source/zotero_related_work.py.txt)；原公共下载路径需 Python、`curl`、`pdftotext`。有权访问本地服务时再使用机器端库 |

档案源码保留真正的历史状态机，采用文本后缀作代码阅读。需要完整续跑时，应在有权访问原输入的环境按冻结协议和已核验的代码快照接续，不在协作仓库安装或开启计时器。管理器中的本地输入名称可用作检索和核对锚点。

原始设计与决策记录定位：

| 原工程相对路径 | SHA-256 |
| --- | --- |
| `docs/RESEARCH_HARNESS.md` | `c6dbbd008e19ff23246975f00dd9e7c0cb7701780dffacb11b9c2283f88dc46f` |
| `docs/AUTORESEARCH_OBJECTIVE.md` | `b425fd0f29b6d1dec6b53632c605aa03763730a85a4a4ee1dcf8ae496565b254` |
| `docs/AUTORESEARCH_PROGRESS.md` | `aac6162c64f82aec813b263bbbcc46facf0daeab2674e63cc400d4e63d7a156f` |
| `docs/AUTORESEARCH_DECISIONS.md` | `3d3851aac89d8df4a9f19c551e35b6d84b1c2bc3c75865f2b4c931c3190bef65` |
| `experiments/autoresearch/SYSTEMD.md` | `c510d313e3661f5ad3d1d6eb5f75d544748450e5b1166c18fd910bcb93e83051` |
| `experiments/autoresearch/research-autoresearch.service` | `7fb34ba62be99d6ff5288de8a983ef0a7cb88efc520c98963fe9d143b6b5b854` |
| `experiments/autoresearch/research-autoresearch.timer` | `a252c0d8cbd06cece83ec94282bcf5cb2ecfa1d3a8503653103e3b884b77b56b` |

## 工作流的来源和判断

同伴项目的 ZIP 封存提交为 `e70b2223227a2f0ef2c2e71fb341500e2ce861a1`，归档 SHA-256 为 `390e8838e7596d2ae8719a4364a9b712afba0063935fcd66960dd94ca9849059`。实际借鉴其多层 Loop 分工、`exp-lifecycle` 的检查点、`subagent-fanout` 的独立检查和 `experiment-autopsy` 的失败归档。协作副本保留自己的执行入口。原项目启动器和个人代理配置留在原档。 [多层 Loop 设计](https://github.com/Wzh2learn/agents_final_tech/blob/e70b2223227a2f0ef2c2e71fb341500e2ce861a1/docs/17_Graph_Engineering_%E5%A4%9A%E5%B1%82Loop%E8%AE%BE%E8%AE%A1.md)

本地设计文档还记录固定评价入口、幂等观察、有限状态和独立复测四条借鉴。面板与统计已冻结、车路独立数据仍欠缺时，确定性编排更适合本地任务。基于单一标量反复改模型的循环容易消耗探索面板，历史流程以逐阶段证据放行。 [Karpathy AutoResearch](https://github.com/karpathy/autoresearch) · [Hugo AutoResearch](https://github.com/hugoferreira/autoresearch) · [Driveline AutoResearch](https://github.com/drivelineresearch/autoresearch-claude-code) · [Outerloop](https://github.com/outerloop-science/outerloop)
