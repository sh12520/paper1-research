# PAPER-METHOD-FREEZE-REVIEW-01 · 基线公平性审查

**状态** · REVIEW / DRAFT。候选方法和强通用基线的同域比较定义可保留。现有开发执行器尚不能承担独立持出评价。本文件未授权生成或执行确认样本。

## 候选方法与共享语义

| 路线 | 固定实现与选择 |
|---|---|
| CURRENT_ON_DEMAND_GRAMMAR_SEARCH | `DepthCursor`，保留类型化生成、状态／时间／资源抽象、搜索期安全规范化、语义归并和惰性停止。 [实现](results/depth3/depth_search.py) |
| GENERIC_ABSTRACT_BEST_FIRST | `GenericCursor(strategy="mrv")`，保留确定性的最小剩余值类型洞展开、有限域分割、共同抽象转移、坐标区间与较强的有限乘积下界、父界继承及终端语义去重。并列时继续处理可能领先的前沿。A2 的单一坐标区间界属于消融。 [实现](results/paper_method_dev/generic_search.py) · [强基线规范](PAPER_GENERIC_BASELINE_SPEC.md) |
| FULL_FLAT | 归档的 `make_plan(...,"FLAT-FEASIBILITY")` 在原公开能力条件下全量评分排序。适配器观察同一评分向量和唯一一次排序。 [评分与排序](results/method_dev_v1/public_search.py) · [适配器](results/paper_method_dev/index_controls.py) |
| GENERIC_INDEX、CONTRACT_AWARE_INDEX | 共用 `QueryCursor`、公开评分和资产验证。两条路线使用各自的归档多维索引与合同感知索引。 [检索实现](results/index_gate/index_query.py) · [索引读取校验](results/index_gate/index_tree.py) |
| A1–A6 | 保持开发版的开关与语义。A5 由公共驱动在已证明目标前缀后继续运行，额外耗时及工作量单列。 [消融实现](results/paper_method_dev/ablations.py) · [运行映射](results/paper_method_dev/run_comparison.py) |

各方法读取同一序列化公开条件和有效深度。depth 1/2 的合法结构域为可由有能力的语法导出、含一至两组机制的规范语义类。depth 3 使用含一至四组的结构域；派生输入仅提高有效搜索深度。共有的 CompactEncoder、公开抽象语义和归档可用性掩码以冻结 DSL 与注册表为准。现有生成模型保留 `set_validity_interval` 并只组合其余四组结构能力的开关，归档资产覆盖这 16 种模式，另含无结构能力模式 0。持出校验要逐实例验证公开模型、配置、注册表和能力范围。 [实例模型](src/instances.py) · [深度游标](results/depth3/depth_search.py) · [可用性资产校验](src/availability_index.py)

精确排序使用 `(binary64 FLAT 分数, 49 字节规范语义键的无符号字典序)`。图的类别编号与该键顺序一致。索引的未展开界包含节点内最小类别号，只有当边界二元组之后没有可能领先的前沿或缓冲条目时才认证。语法方法以严格大于边界的未展开分数下界处理并列，再为同键合同恢复固定的规范见证。冻结复核应保留索引二元界的原始分数和类别键。开发适配器在已核对真实二元界时曾为旧标量检查器临时传入 `nextafter`，归档的证书仍保留真实二元界。不得把这个兼容值登记为真实的公开分数下界。 [共同评分](results/grammar_gate/grammar_search.py) · [索引界](results/index_gate/index_query.py) · [适配器检查](results/paper_method_dev/run_comparison.py)

公开检索只接收允许的公开投影。待重放的精确前缀进入同一协议桥接器，复用 27 次静态 B2 检查、原验证器、每批至多 16 份合同、预算检查点 100/500/1000/5000 与双边接受规则。已见候选的 V1–V4 可行性、双方接受及选中见证的状态机复核和搜索正确性分开。候选分数等同于原排序代理分数。可能缺失的后续结构候选以不足前缀记账。合法域短耗尽或已在可用前缀内终止时才可认定完整协议重放。因搜索中止且需继续取候选的查询保留未知结局；已经认证的较短前缀仍可重放。 [公开投影](results/method_dev_v1/runtime.py) · [协议桥接](results/grammar_gate/protocol_adapter.py) · [共同验证器和双边协议](results/method_dev_v1/private_protocol.py)

## 开发证据与资源限制

| 比较 | K=500 证书 | 开发资源条件 |
|---|---|---|
| depth≤2 当前方法 | 80 全长，16 短域，96/96 | 12 s、2,048 MiB 工作集、300,000 展开、180,000 前沿条目 |
| depth≤2 强通用 | 76 全长，16 短域，92/96。其余 4 个达墙钟上限 | 同上 |
| depth≤2 三条图基线 | 每条 80 全长与 16 短域，96/96 | 同墙钟和内存上限；索引另应用节点访问和前沿限制；FLAT 扫描无搜索树 |
| depth 3 当前方法 | 19 全长、5 短域，24/24 | 45 s、2,048 MiB 工作集、2,000,000 展开、260,000 前沿条目 |
| depth 3 强通用 | 0 全长、5 短域，5/24。其余 19 个触及前沿上限 | 同上 |
| depth 3 FULL_FLAT / GENERIC_INDEX / CONTRACT_AWARE_INDEX | **N/A** | 暂无完整深度三图和对应索引资产 |

展开与前沿按实现定义记账。当前语法游标分别报告形态展开、赋值展开和分区探测；通用基线使用类型洞展开和完整语法叶访问；索引使用图节点访问与记录触达。不得用某一种计数单位代替另一种。两种无图方法的前沿限额是固定预算政策的一部分，depth 3 的覆盖差异依赖该政策。开发程序在合作检查点执行限制，强通用路线曾在检查前短暂记录 260,005 条前沿；这类过冲不能作为按更高限额取得证书的依据。内存是 Windows 工作集采样值，另有进程期峰值。 [开发计划](results/paper_method_dev/development_plan.json) · [所有检查点和原因](results/paper_method_dev/per_query.csv) · [比较报告](PAPER_DEVELOPMENT_COMPARISON.md)

全计划含 1,248 条方法×查询和 4,800 个检查点。4,590 个为全长或短域精确证书，210 个受限，`UNSOUND` 为 0。强通用基线还通过了 15 个缩减域核对。额外下界审计涉及 1,128 个前沿状态，其中 1,044 个有合格后代，未发现不安全的界或空域裁剪。在开发主比较中，双方共用能力条件、时间和工作集上限，且按固定顺序轮换串行查询。暖态图工作者与无图工作者各有驻留开销，空闲进程仍占内存。同前缀的协议重放只鉴别搜索输出的一致性，46 条开发记录前缀不足以到达首个预算检查点。 [基线正确性](PAPER_BASELINE_CORRECTNESS_REPORT.md) · [通用下界核对](results/paper_method_dev/generic_bound_checks.json)

## 固定成本、冷启动与适用范围

| 费用边界 | 开发证据及确认报告要求 |
|---|---|
| 离线完整图／可用性 | 图预计算 198.097 s，序列化及统计 12.211 s，17 个可用性／见证资产构建 943.910 s，共计 1,154.218 s。记录物理字节、构建硬件及审计出处。 |
| 索引构建和存储 | 共享特征数组 51,583,460 B。通用树构建 8.933 s、独立树数组 51,019,057 B；合同感知树 10.343 s、55,036,723 B。两树共享一个图与一份特征库，部署汇总只计一次共同资产。 |
| 冷加载 | 固定开发查询的五个独立新进程有身份与证书核对。分别测量图、可用性、公共基底及索引加载和首查询，并注明文件缓存未控制。该诊断是每方法一次。 |
| 暖态查询 | 相同 K=500 和冻结算法。96 条原深度查询的观测总秒数为 FLAT 65.127、通用索引 29.585、合同感知索引 17.485、当前方法 23.053、通用合成 158.984。通用合成总数含四条受限尝试；其总秒数为实际工作量。 |
| 多查询摊销 | 分列新部署 `B_graph + B_availability + B_index + L + Σ T_i` 和已有资产的 `L + Σ T_i`。相同认证覆盖的场景才可解读为交付速度比较。在线超限与内存纳入完整面板。 |

完整图缺失，或能力条件使现有归档图／索引不适用时，无图方法可以从冻结 DSL、注册表及公开能力条件启动。此为系统适用范围与资产依赖上的优势。暖态已建库的合同感知索引在这组开发查询用时更低。 [离线、冷态和暖态审计](PAPER_COST_FAIRNESS_AUDIT.md) · [冷启动记录](results/paper_method_dev/cold_start_costs.json)

## 确认前的执行封口

1. **持出准入与执行器。** 当前 `run_comparison.py` 仅接受固定 PILOT 文件和 96+24 个原 ID，校验旧 CONFIRM 保持关闭，且比较器依赖已封存的每个开发查询和其历史候选计数。实例生成器对旧 CONFIRM 明确拒绝，图装载使用现有工程/PILOT 执行快照。独立方法确认需要新的已批准输入路由与授权绑定，不能复用旧数据通道或更改其授权。输入文件和方法选择均应按身份模板显式校验。 [开发执行器](results/paper_method_dev/run_comparison.py) · [种子授权守卫](src/instances.py) · [图快照检查](src/execution_snapshot.py)
2. **未见实例的证书复核。** depth≤2 用隔离的 FULL_FLAT 参考重算规范键、长度、见证、分数位模式及顺序。depth 3 的图基线保持 N/A，须独立对保存的前缀逐项重算合法性、规范键与 FLAT 分数，并审计前沿／缓冲最小界和短耗尽证据。现有 `validate_cut` 校验摘要、边界与快照字段的一致性。提交仅有自报最小界时，无法据此独立核验未穷尽的整个搜索覆盖。持出执行方案需确定可复查的停止见证、异常处理及受信追踪边界，核对这些信息与所绑定的代码。可利用独立缩减域或流式可行的小域，不要求构造完整 depth 3 图。 [证书检查器](results/depth3/certificate_report.py) · [Depth 3 停止条件](DEPTH3_SOUNDNESS_REVIEW.md)
3. **限额、异常与恢复。** 当前暖态控制器通过阻塞管道接收子进程结果，没有已验证的持出批次外部 watchdog。合作式探针会在后续检查点发现超限，部分 NumPy 或 Python 操作不能中途切断，异常退出可能导致整批停机。现有恢复通过路径存在性跳过已写结果。持出作业恢复时需对提交清单、实例／深度／方法、版本、状态及结果摘要一致性做校验，记录有界停机和异常退出；进一步以旧开发数据完成断点、卡死、损坏提交、资源超限的演练。现有冷诊断使用的 Windows Job Object 管理是可复用依据。 [暖态执行器](results/paper_method_dev/run_comparison.py) · [探针与原子文件替换](results/grammar_gate/run_search.py) · [冷诊断进程管理](results/paper_method_dev/cold_start_diagnostic.py)
4. **可复现资产。** 将所有方法、消融、语义引擎、公开评分、协议和验证器的源码纳入哈希闭包，附配置、图、可用性、索引、参考和执行器指纹。开发比较使用 CPython 3.12.14、NumPy 2.3.5 并限制数值库线程。版本串的摘要用于检测版本，复现锁还应验证相应可执行文件、运行时和原生库的内容。确认前锁定机器、数值环境、并列顺序和调度，并在只含已用开发数据的非计分演练中复核这些设置。 [开发版本和摘要](results/paper_method_dev/development_decision.json) · [执行快照字段](src/execution_snapshot.py)

本审查通过了候选比较定义的同域核对。持出执行路由、监督恢复和独立证书复核尚无已验证闭环。现有开发报告和快照保持只读，未生成任何确认数据。
