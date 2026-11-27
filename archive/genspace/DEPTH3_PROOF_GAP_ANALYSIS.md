# Depth 3 前沿覆盖证明缺口

`DEPTH3-FRONTIER-PROOF-CLOSE-01` 审计既有 24 个冻结开发查询。历史 `DEPTH3-FEASIBILITY-01 = DEPTH3_PARTIAL` 仍有效。旧开发审计记录了 72 个原生精确检查点，五个短域另有独立穷举证据。对一般 rich 查询，历史数据足以复核**已输出前缀**，但不足以独立证明**前缀之外的合法域都被检查或安全排除**。这是历史证明对象的信息缺口。

## 现有接口实际提供的证据

| 接口及位置 | 可核对内容 | 对完整性的限制 |
|---|---|---|
| `results/depth3/depth_search.py::DepthCursor.next_contract`, `_frontier_lb`, `metrics` | 游标取 shape heap、assignment heap 和展开中状态的下界最小值。只在最小未决下界严格大于待发分数时发出候选。精确候选按 `(binary64 score, packed semantic key)` 排序。 | 一个最小值只约束**当前存入**队列的状态。若合法根分支、子分区或模板早已漏装，队列最小值和计数仍可能一致。 |
| `results/depth3/run_depth3.py::ObservedStream._snapshot` | 在固定 K 记录最后一条的分数与语义键、最小未决下界、未决数、最先缓冲条目、穷尽标记及用分数位和 key 算出的前缀摘要。 | 摘要绑定前缀。缓冲首项只承载一个边界证据。输出未枚举队列成员、父子覆盖、剪枝或合并依据。 |
| `results/depth3/certificate_report.py` 与 `DEPTH3_EXACT_CERTIFICATES.md` | 对冻结见证重新规范化、编码，复算 NumPy FLAT `_proxy` 的分数位，核对紧凑语义键唯一、排序、摘要及边界条件。 | 对未打开状态的覆盖依赖归档生成器维持其游标不变量。它没有读取证明对象来重建整个剩余域。 |
| `results/method_holdout_readiness/unseen_verifier.py::verify_cover` (`typed-cover-v1`) | 裁判从唯一的 DSL 根 `ClauseHole` 开始，独立重建每一个具体 AST 展开的子分区。接收完整叶、经重算且严格超过截止分数的下界节点，以及独立证明没有结构类的终点。它既能核对摘要，也能核对局部覆盖。 | 历史 rich 结果未附覆盖对象。这个 v1 格式也没有为按需形状、符号等价类、模板共享及 profile 掩码补集提供紧凑表示。原独立复核因此对缺证 rich 检查点返回 `BLOCKED_MISSING_INDEPENDENT_FRONTIER_PROOF`。 |

## 从根空间到截止前沿必须核对的义务

| 缺失的证据 | 冻结实现如何处理 | 独立复核所需证据 |
|---|---|---|
| 根空间与子节点覆盖 | `results/depth3/depth_search.py::shape_children` 按固定语法顺序展开第一个未决 `ClauseHole`，保持 `Static` profile 为符号占位，结构参数由 `AbstractSemantics.expand` 提供。 | 从深度 3 根独立重建每个构造器、类型、公开参数、剩余深度与公开能力允许的选择。每个可行分支必须完整归入继续展开、处理完的形状或有可核验理由的终点。仅保存实际展开的形状 ID 会遗漏这项义务。 |
| 参数与 profile 分区 | `DepthCursor._compile` 对可观察 profile 槽枚举等价关系并生成模板。`DedupCursor._expand` 对未赋值 profile 域递进细分，保持不同等价块之间的全异约束。 | 对每个已处理形状重建限制增长串，核对它们覆盖全部可行相等关系。再逐模板检查已完成赋值和未决掩码的并集覆盖全部合法赋值，检查无重叠、无越界和无遗漏。 |
| 安全排除 | `AbstractSemantics` 冻结能力供应/参数语义并建立形状包络。`DepthCursor._push_shape` 排除已证明无目标机制组的子空间。低下界优先，剩余高下界区域留在未决队列直至排序截止。 | 从冻结 registry、作用域和正向谓词规则重建能力约束。确认每个缺失结构能力或组数不合格的分支确实无合法目标完成式。对仍有合法完成式的未决分支必须逐一重算保守下界。V4/V5 通过率或协议结果不能据此排除候选。 |
| 语义合并与最小见证 | `DepthCursor._compile` 缓存完整模板 `(key[:25], cells, visible, groups)` 及所有原始见证配方。`observed_slots` 保留根及每个 `If` 子式规范化读取的 profile 位置，因此保留隐藏相等约束。 | 使用相同冻结解释器重算全合同角色/作用域、逐格活动角色、时间平移、offload、规范化状态和公开分数输入。对每条配方检查隐藏等价块的全异扩展合法，重建字典序最小原始见证后再规范化。相同 envelope 或相同摘要不能作为部分程序合并依据。 |
| 最终未探索域与排序 | 原始证书只记录 `frontier_min_lb`、计数、缓冲首项和 `full_domain_exhausted`。 | 独立覆盖剩余形状和剩余赋值。每个未决区域的保守下界必须**严格**高于截止分数。相同分数的完整缓冲条目必须按规范语义键排在边界之后。对于短域必须证明前沿和缓冲均为空，全部合法目标语义均已出现在结果中。 |

相关代码位于 `results/grammar_gate/abstract_semantics.py::AbstractSemantics`、`results/grammar_dedup/dedup_search.py::DedupCursor` 和 `src/state_machine.py`。可证明的作用域限于冻结的六状态—时间格和公开角色谓词。任意替换 registry、扩大 DSL，或将抽象解释器称作真实网络履约证明均超出本审计。

## 浮点与历史协议边界

- 完整候选以冻结 `_proxy` 复算 binary64 位模式。保守下界按公开包络重建。`GRAMMAR_BOUND_SPEC.md` 区分同顺序单调计算与重新结合的逐格联合界。后者依赖已给出的有限域误差向下裕量，裁判仍须核对后才允许跳过该区域。等分时逐格放宽下界不能排除该区域。同分合同的先后顺序由完整语义键决定。
- `run_depth3.py::run_case` 的历史双边协议允许继续消费 K=500 之外的结构候选，并归档到 5,000 次精确验证的预算检查点。只读、公开的信息重放只对 K=10/100/500 提供前缀证据。逐字节核对原 sealed 文件含协议输出可证明历史工件未变。该核对和前缀匹配本身不构成对 K=500 之外候选流或完整历史协议的重新执行。
- 五个短域的独立穷举可按 `DEPTH3_GATE_INTERPRETATION.md` 和 `results/paper_method_review/short_domain_verification.json` 复核。一般 rich 查询仍须提供逐分区的完整覆盖。哈希绑定只能发现字节变化。裁判必须逐分区核对语义才能关闭缺口。
