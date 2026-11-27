# 论文 1 独立确认实验 · 最终人工审批摘要

**2026-11-19 · `METHOD-FINAL-FREEZE-APPROVAL-01` · `APPROVAL_PENDING`**

拟审批范围为 `GENSPACE-METHOD-HOLDOUT-V1` 的方法确认。审批对象包括待签的冻结清单、主要终点、固定身份、执行和资源方案。当前 `METHOD_HOLDOUT=false`、`CONFIRM=false`。授权文件中的独立 release 与 readiness 批准摘要均为空。

## 候选版本核对

| 对象 | 上轮冻结入口或依据 |
|---|---|
| CS-ODS 当前方法 | `CURRENT_ON_DEMAND_GRAMMAR_SEARCH`，`results/depth3/depth_search.py::DepthCursor`。源码 SHA-256 为 `abc26e9793376863321d04701cb011075fef52c4447c8311eb8cf7be5baa1631`。 |
| 通用基线 | `GENERIC_ABSTRACT_BEST_FIRST`，`results/paper_method_dev/generic_search.py::GenericCursor(strategy=mrv)`。源码 SHA-256 为 `9e10d9063a5958103ea39c0cea587e15ed837743aa8e4e062bf65eb879754331`。 |
| 六项消融与三项图方法 | A1–A6、Full FLAT、Generic Index 和 Contract-Aware Index 的实际入口与上轮候选相同。Depth 3 的三条图路线为 N/A。 |
| 共同合同语义与协议 | DSL、能力注册表、资源模型、FLAT binary64 评分、规范语义身份、tie-break、exact verifier、B2 与双边协议均随候选源码、配置及数据资产绑定。 |
| 证明与执行 | 上轮 base 快照覆盖 Windows Job 暖态监督、事务恢复和统计实现。Depth 3 附录锁定公开证明生成、独立裁判、签名归档和接入入口。 |
| 身份与依赖 | 2,880 个基础身份和 480 个派生身份由固定模板绑定。CPython 3.12.14、NumPy 2.3.5、运行时二进制、逐文件摘要和线程设置随清单锁定。 |

已重验 148 个候选源码、75 项候选资产、16 个 base 工程文件、8 个证明附录文件和两套逐文件运行时摘要。候选源码树 SHA-256 为 `320f956834af272f24b43db9721bbd67247af1fd159e52fe776a5bdd6fa26ca7`，与上轮一致。开发证据为 24/24 查询、72/72 检查点、rich 12/12、两类证明各 11/11 篡改拒绝、24/24 协议重放一致。 [冻结清单](METHOD_FINAL_FREEZE_MANIFEST.json) · [准备审查](METHOD_HOLDOUT_FINAL_READINESS_REPORT.md)

## 请逐项审核的主要终点

| 终点 | 固定样本及 K | 配对效应 | 全部通过条件 |
|---|---|---|---|
| A · 在线搜索效率 | 24 个 rich-depth2 配置各 30 对，**720 对**，K=500 | 配置内均值后 24 配置等权。认证时间取最低 1 ms，获归属的未认证取 12 s。效应为 `log(T*_generic / T*_CS-ODS)`，指数化为几何时延比。 | Bonferroni 校正单侧 97.5% 下界指数化后严格 **>1.25**。CS-ODS 认证率 **≥95%**，至少 684/720。CS-ODS 减通用基线的观测认证率差 **≥−2 个百分点**，整数成功数差至少 −14。 |
| B · Depth 3 认证覆盖 | 48 个原深度 2 配置各 10 对，**480 对**，K=500 | 配置内均值后 48 配置等权。以 `C_CS-ODS − C_generic` 计算风险差，完整和已证穷尽短域均计认证。 | Bonferroni 校正单侧 97.5% 下界严格 **>+20 个百分点**。CS-ODS 认证率 **≥95%**，至少 456/480。 |

两项均须通过。现有 Hoeffding 门禁每项单侧 α=0.025，另报每项名义双侧 95% 区间。分层确定性 bootstrap 继续按配置内重抽整对、配置等权，保留原 10,000 次敏感性分析口径。任何 `UNSOUND`、未核验记录、不可归属异常、无法核清缺失、配对不一致或独立性未核实均阻断正式通过。可归属且证据齐备的超限继续按原规则处理。 [预注册候选](METHOD_FINAL_PREREGISTRATION.md)

## 执行和资源审批

共 **35,520 次预定评估**及 **138,240 个检查点**，暖态公共搜索串行上限 **153.6 小时**。Depth 3 证明预计额外生成 **43.34 分钟**、首次复核 **59.66 分钟**。若另一阶段从新进程全量重验，再计 **59.66 分钟**。480 个查询的点估计为 **195.11 MiB** 压缩归档，两份合计约 **390.22 MiB**。每查询单一签名归档在同查询涉及的 K 与方法之间复用，验收仍逐条比较原生输出。 [执行计划](METHOD_FINAL_EXECUTION_PLAN.md)

10 GiB 可容纳已测量外推的一般工作档。证明格式读入上限折合单份归档 **45 GiB** 的保守边界，须核准工作盘的额外余量、临时文件和 IPC 留存，以及独立备份容量。正式主机与时段、配对计时独立性审计、独立备份落点与恢复验收均待人工确认。执行入口消费由独立托管方另行审批、封存和发布的输入；当前模板仅锁定身份。签名或批准记录须引用最终文件字节的完整 SHA-256。 [人工授权模板](METHOD_CONFIRMATION_AUTHORIZATION_TEMPLATE.md)
