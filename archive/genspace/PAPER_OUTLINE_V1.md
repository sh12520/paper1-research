# PAPER-METHOD-REVIEW-01 · Paper outline v1

拟题 · **Capability-Grounded Contract Synthesis for Intent Negotiation with Exact On-Demand Ranking**

论文的主要问题是在冻结能力与公开运行条件下，能否按公开目标精确生成供双边协商消费的结构合同，而无需完整语义图。分别用搜索证书和验证器／协议结果支持搜索和协商主张。 [贡献边界](PAPER_CONTRIBUTION_BOUNDARIES.md)

## 1. Introduction

- 提出固定 scalar 维度的合同即使扩大取值也可能无法覆盖有条件、分阶段或跨资源分配的协议。使用一个已有开发案例说明合同在状态／时间上的差异。以 B0、B1、B2 和诊断性 FULL-O1 的分工交代研究动机。
- 解释完全物化和评分的在线成本，并说明完整图在高复用量下也可能值得。文章比较按需生成与已物化图上的检索，因此同时报告离线成本、在线成本和证书覆盖。 [FLAT 审计](FLAT_BASELINE_AUDIT_REPORT.md)
- 列出三个领域贡献。基于能力的合同语义、保证公开顺序的惰性合同流、与固定双边协议的接口。明确证明的有限 DSL 假设与证据的开发性质。 [贡献边界](PAPER_CONTRIBUTION_BOUNDARIES.md)

## 2. Related Work

- 说明 intent formulation、translation、orchestration、assurance 的分工。把本文定位在给定公开能力条件下生成候选合同及 benchmark 验证。 [RFC 9315](https://www.rfc-editor.org/rfc/rfc9315.html)
- 将 typed synthesis、DSL 语义、部分程序抽象与等价状态消除分别定位。比较应共享可执行语义，再检验专门的合同抽象能否提高搜索效率。 [Syntax-Guided Synthesis](https://www.microsoft.com/en-us/research/publication/syntax-guided-synthesis/) · [Semantics-Guided Synthesis](https://arxiv.org/abs/2008.09836) · [Program Synthesis using Abstraction Refinement](https://arxiv.org/abs/1710.07740) · [egg](https://arxiv.org/abs/2004.03082)
- 说明 best-first 与 admissible bound 的通用性，区分已有记录上的 exact Top-K 检索和按需生成新记录。用相同查询排序的两种索引基线比较这一取舍。 [Hart、Nilsson、Raphael, 1968](https://doi.org/10.1109/TSSC.1968.300136) · [Optimal Aggregation Algorithms for Middleware](https://arxiv.org/abs/cs/0204046)
- 单独定位 intent negotiation 和双边接受机制。本文复用既有协议，对照公开候选流的构造方式。协议设计本身不列为新贡献。 [方法对照设计](PAPER_METHOD_EVALUATION_DESIGN.md)

## 3. Problem Formulation

- 定义序列化输入、public/private 边界、能力 availability、允许的算子参数及深度预算。固定公开竞争目标为 FLAT score，并按规范键消解同分。
- 定义查询合格结构域 `D(q,d)`、精确前缀长度 `min(K, |D(q,d)|)`、短域穷尽证书、资源停止及无效证书。B2 通过独立 static 路径进入已有协议，结构流在协议需要时调用。
- 区分旧 FLAT 一至两组结构候选域、depth 3 一至四组扩展域及同一机制组条件下的成对深度比较。定义 V1–V5、verified agreement 及 Nash。 [Depth 3 正确性审查](DEPTH3_SOUNDNESS_REVIEW.md)

## 4. Capability-Grounded Contract Semantics

- 列出六个构造器及其类型和上下文。用一张状态／时间表追踪 `If` 和 `Offload` 组合下的活跃角色、whole footprint、RAN/FH/EDGE 作用与公开约束。
- 定义完整签名和局部时间重定位，说明相同执行 profile 为何不足以建立语义等价。给出上下文同余、不可修复的非法条件及适用的冻结前提。
- 将 `benchmark_verified` 的运行含义限定为对抽象状态机和该实例的 V1–V5 校验，以及对有限 guarded schedule 的执行解释。 [能力语义](CAPABILITY_SEMANTICS.md) · [上下文同余](SEMANTIC_CONGRUENCE.md)

## 5. On-Demand Search Method

- 给出从 typed holes 和 capability-enabled productions 到骨架队列、符号等价划分、profile 赋值队列和候选发出的伪代码。画出公开搜索与持有私有偏好的协议端之间的数据边界。
- 说明为什么部分节点拥有相同 envelope 不能直接合并。解释保留所有影响 `If` 等价判断的观察点，以及从多种语法来历恢复稳定代表的方法。
- 说明公开分数下界对 scope、能力角色、活跃单元和 profile 的放松，及 binary64 舍入和并列分数的处理。 [合同去重证明](GRAMMAR_DEDUP_SOUNDNESS.md) · [FLAT 下界](GRAMMAR_BOUND_SPEC.md)

## 6. Correctness and Complexity

- 证明 transfer 覆盖、模板实例化在合法域下完备、去重保持精确签名和 lexical witness、所有未处理完成式被 frontier 表示，以及严格分数分离或穷尽给出的证书。
- 分别报告数学假设、独立小域枚举、旧 FLAT 回归及完整语义图可用边界。单个证书证明其前缀，未获得证书的运行按触发原因保留。
- 给出有限语法计数和查询工作量的上界项。混合两个二元和三个一元算子时，完整 AST 数满足 `T[d] = P + 3 T[d−1] + 2 T[d−1]^2`，其中 `T[0] = P` 为静态 profile 数且每种算子参数一个取值。剪枝和惰性求值影响实测访问量，语法数不能用作深度 3 精确语义数或实测耗时。 [Depth 3 正确性审查](DEPTH3_SOUNDNESS_REVIEW.md) · [Depth 3 搜索成本](DEPTH3_SEARCH_COST_REPORT.md)

## 7. Experiments

| 小节 | 证据与产出 |
|---|---|
| Development lineage | 简述固定空间与结构候选的诊断、DG-PCE／FLAT 瓶颈、索引与无图搜索的审计轨迹。保留历史 FAIL、PASS 与 `DEPTH3_PARTIAL`。将事后短域解释另列。 [门禁解释](DEPTH3_GATE_INTERPRETATION.md) |
| Exactness | 对比语义集合、有序 Top-K、binary64 分数、稳定并列处理、代表合同及协议轨迹。分开报 full-length、exhausted-short、resource-limited 和 unsound。 |
| Search efficiency | 对 Full FLAT、泛用多维索引、合同索引、通用 partial-program best-first、当前搜索和六个消融，报告工作量、时延、峰值内存及构建／存储。用完全相同公开查询、分数和统计口径。 |
| Negotiation | 用同一 verifier、接受规则和预算分别报 verified agreement、Nash 及 gap、精确验证次数、proposal rounds 和未知状态。公开 Top-K 结果与协议结果各用一张表。 |
| Scalability | 分开比较总样本和预先定义的高成本子集，以及相同机制组投影下的深度变化。depth 3 证据来自可审计证书与小域独立参照，完整 depth 3 FLAT 留空并解释原因。 |

开发结果用于解释设计选择。确认性样本、门槛和统计区间待前瞻冻结后执行，正文把待验证内容写作评价计划。 [方法对照设计](PAPER_METHOD_EVALUATION_DESIGN.md) · [独立预注册草稿](METHOD_CONFIRMATION_PREREGISTRATION_DRAFT.md)

## 8. Limitations

- 有限状态／时间与冻结注册表限制了正确性和工程外推。真实网络中的并发、故障、异构供应商、时钟和动态资源状态需要另行验证。抽象 benchmark 验证无法作为实际部署的履约证明。
- 有限语法中的精确前缀取决于下界质量、去重和 frontier。全域最坏工作量可能仍很大。小域可认证短前缀，资源耗尽的未认证后缀保持未知。
- 从已开发查询不能估计独立提升。Depth 3 合同新颖性、协议增加和 Nash 提升是三个不同问题。一份新被接受合同仅支持合同存在性。 [新增合同分析](DEPTH3_NEW_CONTRACT_ANALYSIS.md)
