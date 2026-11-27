# 第三轮修订历史

| 步骤 | 变更与依据 |
|---|---|
| 定位稿件和意见 | 以前轮 `PAPER1_REVISED_FINAL.docx` 和对应可重建源为底稿。读取用户附带的原审阅意见。保留原 Word、PDF、Markdown 和源码字节。 |
| M1、M4 与书目 | 以发布方元数据及原文修订 §§1–2、6.1、6.4、7.4 和结论。增加两条 2026 年近邻，修正 Higham 的出版社。 [文献核验](work/literature_round3_audit.md) |
| M2、M3、M6 | 对现有档案只读配对和聚合。增加表 3 的三段成本、§6.7 的实际合同、六格负载、封存消息与表 6 的协议结果分母。 [计时配对](Supplementary_Materials/S9_depth3_audited_stage_summary.json) · [合同与协议核验](work/round3_m3_m6_evidence.md) |
| M5 | 重写 §§5.2–5.3 的数值与覆盖论证。附 S12 运算图、算术误差界和可执行边界复核。 [形式化复审](work/round3_math_review.md) |
| 图表和读者入口 | 增加 §3 阶段路标和符号说明。图 2、3、5 从前轮按位保留的数据重绘，统一 S 编号。表 2 保留，原表 3 的消融表在本轮编为表 4。 |
| 二位视角复审 | 通信复审明确首时段 0.10 为 EDGE 角色附加负载，并保留 O1 已可解。形式化复审将浮点最后减法明确放在最近值取偶假设下。三段合计的措辞改为不同执行的分阶段成本，保留 0.749 s 为此前的观察停止时钟，表 3 用 0.748 s 的原生取证时钟。 |
| 三格式输出 | 统一从 `work/manuscript_round3_source.md` 生成，两套排版环境各自实渲染复核。创作文档与审查派生文件均位于本轮目录。 [最终质量审计](ROUND3_FINAL_QUALITY_AUDIT.md) |

最终冻结清单 SHA-256 仍为 `60bef57c1566be900f41b336f9f74b41dc80076132d3f48864d75b0292aae533`。授权文件仍为 `bc79872fbed17a017397e20e68c35b6f78668636dedf690bd4319f514d2101d4`。 [冻结绑定核验](work/frozen_bindings_check.json)
