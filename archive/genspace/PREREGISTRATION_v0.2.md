# 预注册草稿 v0.2：GENSPACE-FAIL-01

状态：**第一轮草稿，未冻结，不授权正式确认运行**。本文件记录拟议门禁与统计口径；实例生成分布、离散 grammar 参数域、物理模型和 utility 参数必须在 pilot 后、任何确认数据生成前完整冻结。Pilot 信息用于发现错误和可行性，不得计入确认分析。根据用户要求，pilot、冻结及新的运行门禁均完成之前，禁止启动 9,600 个正式实例。任何调整保留版本记录；调整后需重新预注册和独立确认种子。绝不把诊断穷举 oracle 解释为提议算法。

## 问题和边界

当固定三维合同及其全值域让步不产生协议时，检查公开 capability 及 typed grammar 的组合是否存在满足双方保留效用、约束和编译要求的结构合同。这个实验评估有限离散模型中的存在性，不证明真实网络部署或一般情形下的有效性。禁止 LLM、ns-3、5G-LENA、TFH 数据，以及使用私有 utility 定向生成候选。方法共享实例和公共状态，只有候选空间不同；utility 只进入独立验收和结果选择阶段。

## 比较与采样

4 families × 3 resource pressure × 2 preference conflict × 2 capability richness × 2 composition depth = 96 configurations。每个 configuration 先用 20 个 paired pilot seeds（合计 1,920 个实例）并单列四个 canonical unit cases；确认阶段每 configuration 用 100 个与 pilot 不重叠的 paired seeds（9,600 个实例）。同一实例的 B0、B1、B2、O1 共用生成后的实例、公有状态、registry 和随机源；不同方法不得重抽状态或偏好。记录实例 ID、seed、配置、方法和输入哈希。负对照以相同实例和偏好为基础，仅按预先固定规则移除结构能力，各方法使用同一负对照 registry。公开的随机种子映射、参数分布及全部数值域在冻结前补全；不可在观察确认结果后修改。

B0 穷举初始固定合同集合 M0；B1 穷举预定义原始三维让步值域 MR；B2 穷举预先公开的扩展 scalar 笛卡尔域；O1 EXACT_SEMANTIC_CAPABILITY_ORACLE 无私有输入地精确枚举配置深度以内全部 benchmark 合同语义类，每类保留规范 AST 字典序最小的 witness；语法枚举只用于独立完整性验证。枚举必须是有限的，语法参数域、深度定义、类型及合法性约束在冻结配置中明确；不得将固定的手选模板称作全 grammar 穷举。V1–V5 依次给出每个候选的首个拒绝层与原因；编译成功亦为 verified 的必要条件。候选数、耗时记录生成和验证的计时边界，结果包括零可行候选。

## 预先指定的指标和估计

每个实例每方法以是否至少存在 verified agreement 计算协议率。固定空间死锁是 B1 无协议；verified deadlock resolution rate 为这些实例中 O1 有协议的比例，分母为零则标记 NA。O1 相对 B1/B2 的增量在同一实例配对计算。对每方法中 verified 候选，独立于候选生成，选取效用乘积 uA × uN 最大者作为报告代表，平局以规范 AST 字符串字典序打破；报告两方 utility 与 Nash welfare（原始归一化 utility 乘积，非减去 reservation），无协议为缺失而非零。Pareto improvement：仅在 B1 和 O1 均存在协议时，O1 的代表合同相对 B1 代表合同双方 utility 均不低、至少一方严格更高的比例；报告分母。结构新颖率：在 resolved deadlocks 中，所选 O1 代表的 ContractSemanticSignature 不属于同一 PublicInstance 的 semantic_set(B2) 的比例；分母为零记 NA。与 witness 的语法形式无关，另报告任一 verified 新颖语义存在率和独立 mechanism labels。AST depth、不同 capability 数、候选数、每层首个拒绝的计数和分布、端到端运行时间按方法及配置报告。

每个 family 的协议率先计算各 configuration 中的 paired 百分点差，再等权平均 24 个 configuration。Bootstrap 95% percentile 区间：对每 configuration 内实例对有放回抽样，每次重算等权 family 均值，10,000 次；四个 family 分别计算，不跨方法独立抽样。bootstrap 随机源固定并记录。门禁仅用确认集，区间为未做多重比较调整的描述性区间；多重门禁结果不解释为统一显著性检验。负对照同样按 family 等权聚合并报告各 configuration。

## 确认门禁（pilot 前草拟）

- A：至少两个 family 的 O1−B1 协议率绝对差 ≥ 20 个百分点，且各自 bootstrap 95% 区间下界严格 > 10 个百分点。
- B：所有 family/configuration 的 B1 死锁实例合并，至少 70% 的 O1 resolved deadlocks 所选代表的 ContractSemanticSignature 不属于 semantic_set(B2)；分母为零则不通过。
- C：至少两个 family 的 O1−B2 协议率绝对差 ≥ 10 个百分点。
- D：负对照下所有 family 的 O1−B1 等权平均差均严格 < 5 个百分点；同时报告各 configuration 差异。所有 static capabilities 完整保留时，要求 semantic_set(O1) == semantic_set(B2) 精确成立；任何差异视为实现错误并阻塞运行。<5pp 仅为额外的协议率 sanity gate。
- E：至少两个 family 各有一对相邻 configuration，二者的 O1−B1 绝对差均 ≥ 10 个百分点；相邻指同 family 且其他参数不变，仅一个参数相邻变化（pressure low–medium 或 medium–high，conflict medium–high，richness sparse–rich，depth 1–2）。逐对列出全部相邻差，不事后更换相邻定义。

整体结论要求 A–E 全部通过。没有通过时如实报告，不将探索性结果升级为确认结果。当前空白或未决定的执行细节必须在 pilot 完成后的冻结门禁之前明确；如 pilot 促成修改，形成新版本，记录原因与时间，确认种子保持未触碰。

为保持集合比较可解释，冻结时必须验证 M0 ⊆ MR ⊆ B2 ⊆ MC，包含全部可执行 scalar profile；对于移除结构能力的负对照，若普通 static 所需的 capability 保留，则 MC 的可验证语义集合应与 B2 一致。因而 D 的 <5 个百分点容忍阈值不是允许已知生成或验证错误的理由：发现正差时必须逐例解释并修复后再运行确认集。

## 版本 0.2：在任何结果之前修改的设计

本草稿取代但不覆盖 `PREREGISTRATION.md`，仍未冻结，也不授权 smoke、pilot 或 confirmation。`composition_depth` 的正式主实验候选为 [1,2]，其余网格保持不变：4×3×2×2×2=96 个配置；Static 深度为 0。旧 depth 3 rich 完整 grammar 的类型合法语法树数量为 48,205,158,042,276，完全语法穷举不可行，因此将 depth>2 留给未来方法扩展，不列入本次 exact confirmation gate。F1–F4 的 If、Delay、Sequence、Offload 基本合同均可用 depth 1 表达，depth 2 允许嵌套组合，足以检验本阶段有限存在性问题。该版本变更在观察任何 smoke、pilot 或 confirmation outcome 之前作出，不基于协议率或其他研究结果。工程测试数据只能用于正确性与性能验证。

`ContractSemanticSignature` 包含所有 3×2 状态/时间守卫的 active/idle、profile 和 offload，规范 capability footprint 使用 role 及公开 descriptor（输入/输出类型、前置条件、效果、scope、resource cost、execution cost），并包含影响硬约束、资源或效用的全部公开执行语义。不得使用私有参数生成或规范化。provider ID 不能决定等价性。精确语义枚举不等同声称可在真实网络执行。对冗余 `If(moving,P,P)` 必须在 V2 和成本之前进行经证明保持 benchmark 语义的规范化，使其语义与 P 一致，不能将冗余条件作为新颖结构；该规范化及其嵌套正确性必须有测试与证明，尚未通过时阻塞。

Mechanism labels 按完整 guard cell 的 profile、offload、active role 与资源/执行成本确定：STATE_CONDITIONAL 表示同一时刻不同状态的 cell 不同；DELAYED_START 表示至少一个状态在初始时刻 idle、此后 active；TEMPORAL_PHASED 表示至少一个状态下相邻两个 active cell 不同，单独的 idle/active 转换不算；OFFLOAD 表示至少一个 active cell 使用 offload；HYBRID 表示满足至少两个前述标签。标签是描述性报告，不替代 semantic non-membership。

能力成本在结构重新设计阶段按预定规则核算：setup/deployment cost 暂定为 0；runtime resource/execution cost 只对实际执行的 state/time branch 收费。该假设并非从 smoke、pilot 或 confirmation 结果中选择，详细定义和适用范围见 `MODEL_SPEC.md` 与 `CAPABILITY_SEMANTICS.md`；若语义等价引理或执行一致性不能证明则禁止进入 smoke。

进入 smoke 前，rich depth≤2 语义库必须完整精确预计算；全域 streaming depth 2 与 DP 的语义集合须完全相等；peak memory <4 GB，预计算时间 <30 分钟，至少 20 个工程 fixture 的 O1 单实例过滤和验证 median <2 秒；完整性、私有信息隔离和 negative control 必须通过。工程 fixture 命名空间独立，不得用于科研结果。即使这些工程门通过，本次 ORACLE-REDESIGN-01 仍禁止运行 smoke；pilot/confirmation 仍须另行履行门禁。
