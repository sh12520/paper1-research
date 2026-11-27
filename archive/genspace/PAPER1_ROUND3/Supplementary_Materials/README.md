# 论文 1 随稿补充材料

本目录与论文的 S1–S12 编号对应。数据均来自已有开发记录。S1–S8 是前一版审阅稿数据的字节副本。S9–S11 提供本轮只读派生的计时、案例和协商摘要。S12 给出可采纳界与覆盖证明的复核材料。整个目录可与论文一同分发。

| 编号 | 文件或子目录 | 对应内容 |
|---|---|---|
| S1 | `S1_method_k500_summary.csv` | K=500 方法结果及观测工作量 |
| S2 | `S2_paired_k500_comparisons.csv` | 共同认证的配对统计 |
| S3 | `S3_depth3_certificate_counts.csv` | 图 4 的全长、短域及达限计数 |
| S4 | `S4_paired_latency.csv` | 图 2 的数据点及证书状态 |
| S5 | `S5_paired_search_work.csv` | 图 3 的细化工作量 |
| S6 | `S6_ablation_k500_summary.csv` | 表 4、图 5 的消融数据及分母 |
| S7 | `S7_engineering_costs.csv` | 图 6 的离线、冷启动和暖态成本 |
| S8 | `S8_source_sha256.csv` | S1–S7 的归档输入及原始 SHA-256 |
| S9 | `S9_depth3_audited_stage_times.csv`、`S9_depth3_audited_stage_summary.json` | 表 3 的 24 个已核对身份和前缀的三段时钟；分别保存搜索停止、原生取证和旧封存取证时钟 |
| S10 | `S10_contract_case/` | §6.7 的 F2 合同、公开容量及六单元的 V4 核算和封存协议消息 |
| S11 | `S11_protocol_replay/` | §6.7 的历史方法—查询回放分母及聚合 |
| S12 | `S12_BINARY64_AND_COVERAGE_PROOF.md`、`S12_check_binary64_bounds.py` | §5.2–5.3 的运算图、覆盖与截止条件、边界检查 |

S9 先按实例标识、公开摘要、原始深度 3 归档摘要及精确排序前缀摘要配对，再在各查询内把在线原生取证、证明生成和裁判复核相加。`audited_stage_sum_s` 是表 3 的总量。三个阶段分别运行。结果排除未连贯计量的解释器启动、父端监督、内存等待和备份工作。`sealed_reference_stage_sum_s` 是替换为原始深度扩展归档取证时钟的敏感性对照，未用于表 3。持出结果与研究种子均未纳入。

`SHA256SUMS.txt` 记录随稿文件的完整摘要。`verify_package.py` 能校验全包及独立重算表 3 的中位数和 p95。
