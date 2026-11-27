# 修订与证据记录

| 版本 | 生成或检查方式 | 证据与状态 |
|---|---|---|
| 原导师审阅稿 | 只读。Markdown 原字节 SHA-256 `78a17e632e63c5e53e9a877e0b8e89cc7f25825528d33c01836857efe605d082` | [原稿](../PAPER1_FINAL_DELIVERY/PAPER1_FINAL_FOR_HUMAN_REVIEW.md) · [原交接](../PAPER1_FINAL_DELIVERY/FINAL_HANDOFF_REPORT.md) · [原质量审计](../PAPER1_FINAL_DELIVERY/FINAL_QUALITY_AUDIT.md) |
| 一审修订稿 | 重写题目、双语摘要、相关工作、数学证明、开发实验解释及局限。原 18 条引用独立核验，补入 5 条合成和通信领域文献 | [一审稿](PAPER1_REVISED_AFTER_INDEPENDENT_REVIEW.md) · [逐项 Major 审查](INDEPENDENT_ACADEMIC_REVIEW.md) |
| 二审和最终稿 | 全篇交叉复查。补正 scope 修复反例、Depth 3 原门禁的 F4 sparse 条件、协议回放的效用乘积口径。收紧摘要的前缀精确性措辞，增加 Higham 的数值误差资料。按同一最终源导出三个格式 | [Markdown](PAPER1_REVISED_FINAL.md) · [Word](PAPER1_REVISED_FINAL.docx) · [PDF](PAPER1_REVISED_FINAL.pdf) · [最终复核](FINAL_ACADEMIC_REVIEW_REPORT.md) |

## 证据索引

| 主张 | 可复核证据 |
|---|---|
| 精确排序范围，类型和 V2–V5，浮点误差及同分处理 | [冻结状态机](../src/state_machine.py) · [公开评分实现](../results/grammar_gate/grammar_search.py) · [Depth 3 光标](../results/depth3/depth_search.py) · [覆盖裁判规格](../DEPTH3_FRONTIER_PROOF_SPEC.md) |
| 共同认证速度、质量域短结果和限额截尾 | [逐 K 封存记录](../results/paper_method_dev/per_query.csv) · [独立重算脚本](work/recompute_experiment_review.py) · [重算结果](work/experiment_recomputed.json) · [短域审计](../DEPTH3_GATE_INTERPRETATION.md) |
| 结构来源及完整空间归因 | [PILOT OFFLOAD 反事实归因](../PILOT_OFFLOAD_ATTRIBUTION.md) · [Depth 3 新增代表记录](../DEPTH3_NEW_CONTRACT_ANALYSIS.md) |
| 实验正确性、统计口径和开发／确认边界 | [基线正确性](../PAPER_BASELINE_CORRECTNESS_REPORT.md) · [证明审计](../DEPTH3_INDEPENDENT_PROOF_AUDIT.md) · [最终预注册候选](../METHOD_FINAL_PREREGISTRATION.md) · [冻结与授权复核](work/confirmation_review.md) |
| 图表和引用的导出一致性 | 六幅图及八份支持表沿用已封存资产并校验复制前后的字节。各图原始输入 11 项 SHA-256 重验。最终正文的 24 条引用与 BibTeX 一一对应。 [资产来源摘要](PAPER1_TABLES/source_sha256.csv) · [引用库](PAPER1_REVISED_REFERENCES.bib) · [三格式机械核验](work/export_checks.json) |

## 确认登记

原 2,880/480 身份计划、Endpoint A/B 口径和资源阈值保持原字节。确认的定义、授权、数据隔离与维护证据分开记录。签署、独立发布和独立备份尚待验收，正文的摘要、§6.6、§7.4 和结论没有使用持出观测。 [人工待办](HUMAN_APPROVAL_ACTIONS.md) · [冻结候选和原稿摘要](work/confirmation_bindings_verified.json)
