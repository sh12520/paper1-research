# 论文 1 证据台账

稿件汇报两个证据层次。开发层用已封存结果解释方法的正确性、可行性与计算开销。独立确认层记录已锁定的身份、终点和资源限制，当前结果为空。论文的公开排序证书、抽象状态机验收和真实网络履约是不同的核验对象。

| 稿件位置 | 可追溯证据 | 读数和解释口径 |
|---|---|---|
| 摘要、§6.2、图 2 | [方法逐项表](../results/paper_method_dev/per_query.csv) · [成对图数据](PAPER1_TABLES/paired_k500_comparisons.csv) | 原深度 K=500 精确交付 96/96 对 92/96。共同认证 92 对，逐对通用／CS-ODS 时延比中位数约 2.57。开发图保留通用基线四个停止点。 |
| §6.2、图 3 | [逐对工作计数](PAPER1_TABLES/paired_search_work.csv) · [图表计数复核](work/stats-appendix.md) | 展开、细化、完整赋值、分区探测和图记录访问分别计量。总开销的比值不能由一个局部计数替代。 |
| §6.2 | [开发比较总表](../PAPER_DEVELOPMENT_COMPARISON.md) · [开发交付摘要](../results/paper_method_dev/development_decision.json) | 1,248 次尝试和 4,800 个检查点。4,590 精确，210 达限。1,248 条同前缀协议记录中，784 完整、418 部分、46 前缀不足。 |
| §6.3、图 4 | [分 K 计数](PAPER1_TABLES/depth3_certificate_counts.csv) · [独立覆盖复核](../results/depth3_proof/per_query.csv) · [证书规范](../DEPTH3_FRONTIER_PROOF_SPEC.md) | K=500 为 CS-ODS 19 全长＋5 短域，通用为 5 短域＋19 达限。24 个 CS-ODS 查询的 72 个检查点独立复核通过，其中 62 全长、10 短域。 |
| §6.3、讨论 | [门禁解释](../DEPTH3_GATE_INTERPRETATION.md) · [历史可行性报告](../results/depth3/DEPTH3_FEASIBILITY_REPORT.md) · [新候选与协议审计](../DEPTH3_NEW_CONTRACT_ANALYSIS.md) | 保留原 DEPTH3_PARTIAL。历史完整长度门槛及小合法域的独立穷尽证据各自可追溯。F3 新合同只有单例存在性证据。 |
| §6.4、图 5 | [消融表](PAPER1_TABLES/ablation_k500_summary.csv) · [消融规范](../PAPER_ABLATION_SPEC.md) | A1–A6 全部列出。A5 的首次证书和继续至穷尽交付按不同状态统计。共同完成配对的开销差与截尾固定分母均保留。 |
| §6.5、图 6 | [工程成本表](PAPER1_TABLES/engineering_costs.csv) · [原公平性审计](../PAPER_COST_FAIRNESS_AUDIT.md) · [证明成本审计](../DEPTH3_PROOF_COST_REPORT.md) | 图构建、索引、冷启动、暖态批次、独立证明是不同成本。已物化图索引在这组暖态队列可以更快。 |
| §3–5、图 1 | [模型与能力语义](../MODEL_SPEC.md) · [理论与代码映射](work/model_method_theory_source_map.md) · [下界规范](../GRAMMAR_BOUND_SPEC.md) | 只有冻结有限 DSL、公开模型和所述舍入条件下的命题。图 1 来自算法接口与解释过程，属于方法示意。 |
| §7.1 | [PILOT 归因](../PILOT_OFFLOAD_ATTRIBUTION.md) · [Depth 3 协议比较](../DEPTH3_NEW_CONTRACT_ANALYSIS.md) | 842 个 B2 失败而 O1 成功的开发实例中，OFFLOAD-only 足够 783，OFFLOAD 必要 721，无 OFFLOAD 仍可达 121。三者是反事实空间上的存在性检验。 |
| §6.6、§7、结论 | [锁定的独立确认方案](../METHOD_FINAL_PREREGISTRATION.md) · [冻结候选清单](../METHOD_FINAL_FREEZE_MANIFEST.json) · [启动审计](work/startup_audit.json) | APPROVAL_PENDING。无 Endpoint A 或 B 持出观测，门槛结果均待判定。作者审阅开发证据无权启动持出实验。 |
| 引文及术语 | [BibTeX](PAPER1_REFERENCES.bib) · [逐条一手来源核验](work/CITATION_VERIFICATION.md) | 文献与标准用于归因和讨论可比范围。个人草案有独立身份标记，合同 DSL 无标准合规或优先权主张。 |

图表重建脚本记录读入原件的 SHA-256。原始查询记录、私有输入及封存结果留在原研究树，导出表保留合法再核验所需的查询标识、指标和源摘要。 [数据来源散列](PAPER1_TABLES/source_sha256.csv) · [图表索引](work/figure-catalog.md)
