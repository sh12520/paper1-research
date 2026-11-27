# 论文 1 导师汇报证据映射

版本依据为第三轮 [正式 Word 稿](../PAPER1_ROUND3/PAPER1_ROUND3_REVISED.docx) 及 [同版 Markdown](../PAPER1_ROUND3/PAPER1_ROUND3_REVISED.md)。S1–S12 指第三轮 [补充材料](../PAPER1_ROUND3/Supplementary_Materials/README.md) 中的编号。早期文件仅用于定位原始表和核验来源，状态以第三轮为准。除明确标注的工程计数和假设示意，结果均为已封存开发数据。

## 正式汇报

| 页 | 论点与证据来源 | 图表定义、分母与限制 |
|---:|---|---|
| 1 | 题目和英文题目取正式 Word 稿封面。 | 署名、导师及日期是待填写字段。 |
| 2 | 研究流程取 §1、§3、§4.3 及图 1。 | 生成器读公开 DSL、能力和资源状态。V1–V4 核验后进入双边协议。私有偏好及接受由 V5 处理。流程图为方法示意。 |
| 3 | 应用和网络角色取 §3.1、§7.3。 | VR 接入拥塞仅作概念示例，无物理量和观测数值。 |
| 4 | 27 个固定档位及六种合同运算符取 §3.1–3.2、表 1 与 §6.7。 | 27 = 3 质量 × 3 时限 × 3 速率。语义示意图用于比较固定参数与状态/阶段/开通时间/执行位置。档位是冻结归一化配置。 |
| 5 | related-work 差分取 §2.1–2.3、[本轮文献核验](work/literature.md) 与下方文献定位。 | 文献矩阵是技术任务与适用范围的对照。MAESTRO/Agoran 不参与本文方法运行比较。 |
| 6 | 表达能力、组合增长及前缀目标取 §1、§3.3、§5.4、§6.1。 | 图示只说明具体技术问题。全文不存在对整个领域缺少候选生成方法的主张。 |
| 7 | 体系结构根据 §3、§4、图 1。 | 区分公共语法生成、公共硬约束检查和各自私有接受。排布示意不含运行指标。 |
| 8 | 六种运算符和固定域取 §3.2 表 1。 | `Sequence + Offload` 为构造机制示意，正文第 11 页另给封存实例。 |
| 9 | 状态和时间取 §3.1–3.2、§7.3。 | 3 槽 × 2 外生状态 = 6 个抽象资源单元。RAN/FH/EDGE 按单元独立核验。容量、负载均归一化。模型不推导真实排队与空口时延。 |
| 10 | F2 首段容量与 B2 V4 拒绝取 §6.7 表 5、[S10 封存案例](../PAPER1_ROUND3/Supplementary_Materials/S10_contract_case/README.md)。 | 一条封存开发实例、27 个静态配置。柱高为归一化 RAN 容量 0.326479、0.932796 和本地最低 RAN 基础需求 0.4。27/27 首次拒绝在 V4。 |
| 11 | 合同 AST、资源轨迹、提案与接受取 §6.7、[S10 数据](../PAPER1_ROUND3/Supplementary_Materials/S10_contract_case/case_evidence.json) 和 [六格资源 CSV](../PAPER1_ROUND3/Supplementary_Materials/S10_contract_case/resource_cells.csv)。 | 第 0 时隙卸载，质量 0.6、RAN 用量 0.3；时隙 1–2 本地，质量 0.8、RAN 用量 0.8。时限 1.0、速率 0.5。应用 0.721810 ≥ 0.655606，网络 0.555552 ≥ 0.527437。6/6 资源单元通过，应用提案后网络接受，1 轮。有效深度 3 队列中首位候选的实际深度为 2，原 O1 已有协议。 |
| 12 | 数量由 §5.4、[语法枚举审计](../ENUMERATION_AUDIT.md) 和 [语义图审计](../SEMANTIC_LIBRARY_AUDIT.md) 核定。 | 完整富能力、固定运算符公共参数域、27 个叶档位、有序子树。`N(0)=27`，`N(d)=27+3N(d−1)+2N(d−1)^2`。累计 AST 为 1,566、4,909,437、48,205,158,042,276；累计语义类为 1,539、1,394,064、未知。数量级刻度是样本计数的 log10。语法树包含随后失格和同义派生。 |
| 13 | 成形流程取 §4、图 1 和算法 1。 | 骨架与 profile 赋值有前沿管理。抽象包络引导下界，按需物化交付。架构图不隐含组件按线性一次处理。 |
| 14 | 包络构造取 §4.1、§5.1、§5.2 以及 [部分合同抽象语义](../PARTIAL_CONTRACT_ABSTRACT_SEMANTICS.md)。 | `Sequence(?, ?)` 为教学示意。资源、质量、角色成本及能力的覆盖是公开、保守的可能性摘要。协议私有阈值不参与。 |
| 15 | 下界方向和结束条件取 §5.2–5.3、[S12](../PAPER1_ROUND3/Supplementary_Materials/S12_BINARY64_AND_COVERAGE_PROOF.md)。 | 公开分值越小越优。例中的分值均为示意数。`LB≤cutoff` 的区域继续细化，严格 `LB>cutoff` 可暂不进入当前前缀。等分可能改变键序或见证。 |
| 16 | 语义签名、上下文同余与完整覆盖取 §3.3、§4.2、§5.1–5.3、[S12](../PAPER1_ROUND3/Supplementary_Materials/S12_BINARY64_AND_COVERAGE_PROOF.md)。 | 共享必须保留全合同能力资质、作用域及逐格选择与成本，不能仅比较配置参数。严格前沿下界与同分规范键共同保证排序。精确前缀、V4、V5 分别回答不同问题。 |
| 17 | 五阶段和双边协议取 §3 开头、§3.2–3.3、§4.3、§6.7。 | 语法 V1、能力 V2、语义 V3、公共资源及硬约束 V4、各自保留效用与双边接受 V5。排序前缀长度 K 与协议核验预算 B 分别计量。 |
| 18 | 方法面板取 §6.1、§6.5、[通用基线规格](../PAPER_GENERIC_BASELINE_SPEC.md)、[开发比较](../PAPER_DEVELOPMENT_COMPARISON.md) 与 S1、S7。 | 五方法共用 domain/score/tie。三图方法依赖预计算全图和能力见证；通用 best-first、CS-ODS 不依赖完整图。Depth 3 三图方法 N/A。96 原深度固定配置实例，24 Depth 3 由其中固定子集派生。 |
| 19 | 配对图从 [S4](../PAPER1_ROUND3/Supplementary_Materials/S4_paired_latency.csv) 重绘；摘要由 [S1](../PAPER1_ROUND3/Supplementary_Materials/S1_method_k500_summary.csv)、[S2](../PAPER1_ROUND3/Supplementary_Materials/S2_paired_k500_comparisons.csv)、§6.2 表 2 核对。 | 原深度、K=500、固定开发 96。CS-ODS 96/96（80 全长+16 短），通用 92/96（76+16）。92 对双方认证中 91 对 CS-ODS 更快，逐对 Generic/CS-ODS 时延比中位 2.565477…（2.57）。点为获证时钟秒；图中若保留达限点则为对应方法观察停止时钟秒，不算进中位比。 |
| 20 | Depth 3 堆叠条图取 [S3](../PAPER1_ROUND3/Supplementary_Materials/S3_depth3_certificate_counts.csv)、§6.3；消融两栏条图取 [S6](../PAPER1_ROUND3/Supplementary_Materials/S6_ablation_k500_summary.csv)、§6.4 表 4。 | Depth 3、K=500、固定 24：CS-ODS 19 全长+5 短，通用 0 全长+5 短+19 前沿达限。A4 原深度高成本 30/30 配对，额外中位 +7,790 展开、+0.629 s；A6 同一队列 28/30 共同获证，+1,647、+0.507 s。展开和耗时使用独立的零起点尺度，只在同一栏内比较。A5 Depth 3 24/24 先取得证书，19 条随后达限，达限子集中证书后额外展开中位 79,750、额外用时中位 43.278 s，两者为耗尽所需工作下界。 |
| 21 | 成本与局限取 §6.3 表 3、§6.5、§6.6、§7.2–7.4、[S7](../PAPER1_ROUND3/Supplementary_Materials/S7_engineering_costs.csv)、[S9](../PAPER1_ROUND3/Supplementary_Materials/S9_depth3_audited_stage_times.csv)、[未解决事项](../PAPER1_ROUND3/UNRESOLVED_ACADEMIC_ISSUES.md)。 | 合同感知索引 17.485 s、CS-ODS 23.053 s 是原深度 96 次暖态观察合计。预建成本和冷启动另列。审计 5.166 s/102.633 s 为 24 条查询逐条在线取证+后置供证+裁判之和后计算中位／线性插值 p95，阶段分开执行。协议率、真实履约和持出均无由此产生的确认性结论。 |
| 22 | 结论和后续取 §7–8、[审稿意见矩阵](../PAPER1_ROUND3/REVIEW_RESPONSE_MATRIX.md) 和 [未解决事项](../PAPER1_ROUND3/UNRESOLVED_ACADEMIC_ISSUES.md)。 | 后续研究为拟议事项。私有反馈协商是未来方向，当前方法的精确排序与协议结果分别论证。 |

## 备用答辩

| 页 | 论点与证据来源 | 图表定义、分母与限制 |
|---:|---|---|
| 23 | DSL 完全式与状态资源模型取 §3.1–3.3、表 1、[能力语义](../CAPABILITY_SEMANTICS.md)。 | 静态叶深度 0，其他深度为 1 加最高子树深度。三个时隙，两个状态，三个归一化资源。 |
| 24 | 算法 1、§4.2–4.3、§5.3、[覆盖证书规格](../DEPTH3_FRONTIER_PROOF_SPEC.md)。 | 伪代码保留 strict inequality、覆盖其余区间、在途展开、短域穷尽；到限保留未认证。 |
| 25 | §5.1–5.3 与 [S12](../PAPER1_ROUND3/Supplementary_Materials/S12_BINARY64_AND_COVERAGE_PROOF.md)、[Depth 3 独立证明审计](../DEPTH3_INDEPENDENT_PROOF_AUDIT.md)。 | binary64 最近值取偶，算术路径最多 61/84 次舍入，保守余量。24 条开发查询 72/72 个检查点复核，其中全长 62、短域 10。覆盖核验独立于搜索队列，使用共同公共语义。 |
| 26 | 全基线及 A1–A6 取 §6.1、§6.4 表 4、§6.5、[消融规格](../PAPER_ABLATION_SPEC.md)、S1、S6、S7。 | 可区分头 K 认证与最终交付。A5 depth≤2 从 96 首次获证到 66 耗尽交付，Depth 3 从 24 到 5。墙钟 s，工作项为展开次数，不与不同路线的单步算力等同。 |
| 27 | §6.6、§7.3–7.4、[未解决事项](../PAPER1_ROUND3/UNRESOLVED_ACADEMIC_ISSUES.md)、[方法持出计划](../METHOD_FINAL_PREREGISTRATION.md)。 | 持出 Endpoint A 预定 720、B 480，均未运行。第二创新点为待提出和验证的研究问题，未与已验证的 CS-ODS 贡献混为一谈。 |
| 28 | §6.2、§6.7 表 6、§7.1、[PILOT 机制归因](../PILOT_MECHANISM_ATTRIBUTION_REPORT.md)、[S11 回放](../PAPER1_ROUND3/Supplementary_Materials/S11_protocol_replay/replay_summary.json)。 | PILOT 开发 1,920 条，其中 842 条 B2 无协议而完整 O1 有；只开放 OFFLOAD 783/842 可解，禁用 OFFLOAD 121/842 可解，故 OFFLOAD 必要 721/842，40/842 至少需要两组。充分和必要可重叠。方法–查询回放 1,248 条：784 全预算、418 部分、46 无输出，各预算分母由可交付记录决定。如展示协议计数，回放仅说明同前缀协议兼容性。 |

## 矩阵文献与数据复算口径

- 可在第三轮 [26 条参考文献](../PAPER1_ROUND3/PAPER1_REFERENCES.bib) 核查 Marsico、Sharma、SemGuS、Mell、Bee/Eco Search、Tranoris 与 Trantzas，以及 Christodoulopoulos 与 Selentis-Boulntadakis 的原始出处。 [2026 跨域合同预印本](https://arxiv.org/abs/2608.09312v2) · [2026 ITU 期刊原文](https://doi.org/10.52953/FPSZ2168)
- MAESTRO 面向异构多方共享网络资源的协商，Agoran 在私有 5G 试验床验证其 Pareto 方案生成、协商和配置。两者提供通信领域背景，评价任务与本文相异。 [MAESTRO](https://doi.org/10.1109/LNET.2024.3503292) · [Agoran](https://doi.org/10.1016/j.comnet.2025.111927)
- 冻结 [方法开发原始表](../results/paper_method_dev/per_query.csv) 的 4,800 检查点归入 1,248 次方法—查询尝试。按实例身份与有效深度配对，证书分为全长、短域穷尽和达限。总计分别是 4,206、384、210。达限与短域是不同状态。
- `work/build_evidence.py` 只读取既有文件，重算配对分数、阶段时钟分布、PILOT 子集、S11 协议分母、A5 达限样本中位数和语法递推。`work/evidence.json` 记录用于作图的原点位与相应摘要，另含输入 SHA-256。所有计算均为描述性证据整理，未进行确认性推断。
