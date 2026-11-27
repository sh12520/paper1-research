# PAPER-METHOD-REVIEW-01 · 论文方法贡献边界

## 当前可主张的结果

在冻结的有限合同 DSL、六单元状态／时间解释及公开能力域内，按需合同搜索可以将候选按公开 FLAT 分数及规范语义键，以可认证的顺序逐个交给既有双边协商协议。在线生成只依赖公开语法、能力及查询状态，通过部分合同的公开下界和等价语义去重延迟实例化，无需预建或读取完整语义图。精确性针对合格结构候选域及其有序前缀。固定开发查询提供了实现证据，支持的深度、机制组投影和资源口径见下表。 [Depth 3 正确性审查](DEPTH3_SOUNDNESS_REVIEW.md) · [Depth 3 证书](DEPTH3_EXACT_CERTIFICATES.md) · [图独立性审计](GRAPH_INDEPENDENCE_AUDIT.md)

| 开发证据 | 可以写进论文的范围 |
|---|---|
| depth≤2 的 96 个固定查询对既有 FLAT 顺序回归，K=10/50/100/500 各 96 对一致。G1–G5 通过。 | 旧排序兼容性限定在原 FLAT 的一至两组结构候选。固定开发查询与既有方法门槛的通过，只作为开发证据。 [Depth 2 回归](DEPTH2_REGRESSION_REPORT.md) · [搜索门禁](GRAMMAR_FINAL_ROUTE_DECISION.md) |
| depth 3 的 24 个既有查询在 K=10/100/500 均得到证书。K=500 有 19 个完整和 5 个穷尽短域。 | 在上限允许一至四组结构的扩展域上，使用规范字节键延伸旧 tie-breaking。原 Depth 3 门禁结论依然是 `DEPTH3_PARTIAL`。 [历史判定](results/depth3/DEPTH3_FEASIBILITY_REPORT.md) · [门禁解释](DEPTH3_GATE_INTERPRETATION.md) |
| 一个被协议选中的合约其签名在全 depth≤2 空间缺失。该查询的 depth≤2 O1 已有协议。 | 支持更深组合可提供新的可接受合同。24 个开发查询中观测到的、相对于 depth≤2 O1 从无协议转为有协议的次数为零。限额中未找到协议的查询仍是 `UNKNOWN`。 [新增合同分析](DEPTH3_NEW_CONTRACT_ANALYSIS.md) |

## A · 使用的通用技术

| 技术 | 论文应如何归因 |
|---|---|
| A*／best-first | 优先队列及选择有希望状态的思路已有先例。本方法按部分合同的最终分数下界做 best-first branch-and-bound。最短路径 A* 的可加 `g+h` 证明体系与本文的下界证明不同。 [Hart、Nilsson、Raphael, 1968](https://doi.org/10.1109/TSSC.1968.300136) |
| Partial-program synthesis | 以语法产生式填补 typed holes，并通过部分程序的描述指导搜索，属于合成研究的通用做法。该方向还已有通过 DSL 抽象语义指导搜索的工作。 [Syntax-Guided Synthesis](https://www.microsoft.com/en-us/research/publication/syntax-guided-synthesis/) · [Program Synthesis using Abstraction Refinement](https://arxiv.org/abs/1710.07740) |
| Abstract interpretation | 用抽象状态覆盖所有具体执行并证明 transfer 的保守性，是已有理论。本文需给出具体状态／时间／资源抽象的定义与正确性。 [Cousot 与 Cousot, 1977](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml) |
| Admissible lower bounds | 用安全下界决定展开顺序、提前停止及认证是通用技术。合同分数下界的推导、适用条件和向下舍入保护才是项目相关内容。 [Hart、Nilsson、Raphael, 1968](https://doi.org/10.1109/TSSC.1968.300136) · [公开下界规范](GRAMMAR_BOUND_SPEC.md) |
| Semantic dedup | 用合同的等价关系缩小搜索域与程序合成和等式推理中的通用机制有关。本文提供的是对合同构造器上下文保同余的等价关系、归一化条件和代表恢复证明。 [egg](https://arxiv.org/abs/2004.03082) · [合同去重证明](GRAMMAR_DEDUP_SOUNDNESS.md) |
| Top-k indexed retrieval | 对多特征记录提供有序 Top-K 是已有任务。泛用索引和合同索引是强对照，尤其适合已有完整记录且重复查询可以摊销建库成本的设置。 [Optimal Aggregation Algorithms for Middleware](https://arxiv.org/abs/cs/0204046) · [本地索引比较](GENERIC_INDEX_COMPARISON.md) |

## B · 候选领域贡献

1. **基于能力的合同语义。** 合同构造器有类型、局部时间与状态语义、资源作用和能力前置要求。规范键记录全合同能力角色、六个单元的活跃角色／profile／offload 及有效性信息。固定公开语义下，替换等价子树需保持父上下文的键和相关检查结果。 [能力语义](CAPABILITY_SEMANTICS.md) · [上下文同余](SEMANTIC_CONGRUENCE.md)
2. **部分合同的状态／时间／资源抽象。** 每个 hole 维护其完成式的保守范围。转移覆盖条件分支、阶段接续、时间平移、有效窗与卸载作用。IF 归一化还要求观察每个条件的子分支键，单看根的实际可达单元会误删可能改变条件消除的 profile 位置。 [部分合同抽象语义](PARTIAL_CONTRACT_ABSTRACT_SEMANTICS.md) · [深度 3 证明](DEPTH3_SOUNDNESS_REVIEW.md)
3. **能力约束下计算的公开分数下界。** 合法能力及深度限定可展开产生式，必要角色和六单元范围约束分数可达到的最小值。模板内部放松共享 profile 的跨单元相等约束以保留下界。精确比较用原 binary64 分数，待处理状态的下界必须严格高于将发出的分数才能跳过潜在同分键。公开物理不可行性由同一 verifier 判定。 [公开下界规范](GRAMMAR_BOUND_SPEC.md) · [深度 3 证明](DEPTH3_SOUNDNESS_REVIEW.md)
4. **无完整图的惰性合同生成。** 只在查询触及骨架时实例化相关位置的等价划分，将相同模板合用可见赋值流，并保留词典序 witness 恢复所需的原始构造信息。此设计提供避免完整图预存的路径，最坏情况下仍可能遍历、评分或保存大量状态。 [合同去重证明](GRAMMAR_DEDUP_SOUNDNESS.md) · [深度 3 搜索成本](DEPTH3_SEARCH_COST_REPORT.md)
5. **可认证的合同流与协商边界。** 验证器、公开搜索与私有接受分开。公开流能按需返回下一个可认证的不同合同，双边协议负责处理预算、验算与接受。精确 Top-K 针对公开目标，接受成功和 Nash 最优需要各自的评价。 [方法对照设计](PAPER_METHOD_EVALUATION_DESIGN.md) · [私有信息审计](PRIVATE_INFORMATION_AUDIT.md)

## 通用合成对照应检验的差分

SyGuS 已使用受语法限制的候选集合，SemGuS 允许外部定义构造器语义。后者可作为表达这类有限合同语义的通用框架。应比较的差分是同一合同语义、同一公开分数和同一协商协议下，六单元 transfer、能力约束、归一化与惰性等价划分能否以更少在线工作重现精确合同顺序。通用 best-first 基线需有可靠的 typed expansion、公开下界、缓存及相同证书接口，并经开发集校准。效果要和索引线的离线建库成本及线上耗时分别比较。 [Semantics-Guided Synthesis](https://arxiv.org/abs/2008.09836) · [方法对照设计](PAPER_METHOD_EVALUATION_DESIGN.md)

## C · 暂无充分证据的主张

| 主张 | 缺少的证据 |
|---|---|
| 首创或文献优先权 | 当前文献核对用于准确归因，尚无完整同领域文献覆盖与优先权证据。 |
| 深度 3 提高协议率或 Nash | 24 个开发查询是用过的固定夹具。深度与原排序域的机制组上限同时变化。深度效应需在同一候选域规则和相同预算下成对测量。选中一份更深合同只支持该合同存在且在 benchmark 中被接受。 |
| 真实网络履约 | `benchmark_verified` 的 V1–V5 与 action schedule 都以冻结抽象状态机为准。部署还需要真实资源、能力接口、故障情况和履约遥测的验证。 [能力语义](CAPABILITY_SEMANTICS.md) · [RFC 9315](https://www.rfc-editor.org/rfc/rfc9315.html) |
| 相对强通用合成器的独立优势 | 尚需同域、同分数、同预算的强通用基线、六项消融和独立样本。现有 PILOT 与后续查询均属开发数据。 [独立评价草稿](METHOD_CONFIRMATION_PREREGISTRATION_DRAFT.md) |
