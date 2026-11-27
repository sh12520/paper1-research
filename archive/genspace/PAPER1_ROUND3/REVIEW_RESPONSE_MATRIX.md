# 第三轮逐项审稿回应

审阅意见以实际附带的 `D:/意图协商论文/论文1_独立审阅意见_2026-11-20.md` 为准，SHA-256 为 `94f1e0715765f360e1465821dd1194a2f94a622a2e43da0f057b2a458ace9f0e`。项目内所述位置未发现同名文件。下列判定来自原文、冻结实现和归档记录的核对。

| 编号 | 判定 | 证据及处置 | 修改后防止的误读 |
|---|---|---|---|
| M1 | `ACCEPT` | 原文核验两项研究。Tranoris 与 Trantzas 的正式 ITU 论文处理意图共创、OpenSlice 编排和测试驱动保障。Christodoulopoulos 与 Selentis-Boulntadakis 的 arXiv v2 预印本处理确定性跨域接口的假设—保证合同及动态切换可行性。§§1、2.1–2.3 补入技术差分。 | CS-ODS 的排序与覆盖证书不被读作 QoS 履约保证或意图共创结果。 [arXiv v2](https://arxiv.org/abs/2608.09312v2) · [ITU 正式期刊全文](https://www.itu.int/dms_pub/itu-s/opb/jnl/S-JNL-VOL7.ISSUE2-2026-A09-PDF-E.pdf) |
| M2 | `PARTIALLY_ACCEPT` | 开销遗漏的担忧成立。按查询身份、公开/实例摘要及原生前缀摘要核对 24/24。先加三段逐查询时钟，再计算中位数 5.166 s、p95 102.633 s、最大值 117.018 s。摘要、§4、§5.3 和 §6.3 区分原生证书与后置核验。 | 三段来自不同进程与既有运行，不能声称直接实测了单次连续端到端墙钟。调度、进程启动、等待和备份另计。保留原在线时钟。 [S9](Supplementary_Materials/S9_depth3_audited_stage_summary.json) |
| M3 | `ACCEPT` | §6.7 以封存 F2 首时段接入受限为例，B2 的 27 项全部在 V4 失败。展示真实结构流第 1 的 `Sequence`/`Offload` AST、六格公开资源与硬约束、16 项结构合同通过公开检查、应用提案和网络接受，以及阈值与归档效用。 | 选合同的实际深度为 2，原深度 O1 已可解。案例的资源和时延档保持归一化基准语义。 [S10](Supplementary_Materials/S10_contract_case/README.md) |
| M4 | `ACCEPT` | §§1、2.3、6.1、6.4、7.4、8 阐明 MRV、公开参数划分、缓存、父界继承、联合因子界、终端去重与共同截止规则。保留 Bee Search、Eco Search 和树自动机等路线。A4 只解释固定架构下精细信息给下界带来的边际作用。 | 主速度结论限于已实现同域基线，不外推成熟合成框架的总体排名。第二类同域强基线属于投稿增证。 [基线及文献核验](work/literature_round3_audit.md) |
| M5 | `ACCEPT` | §§5.2–5.3 与 S12 给出两条运算图、61／84 次舍入上限、有限叶值、次正规误差项、保守余量与最终减法。补写根分区覆盖、在途展开、同分细化、严格结束和短域穷尽。脚本对既定数学边界独立交叉检查。 | 浮点推导依赖冻结域及 binary64 最近值取偶。Depth 3 裁判独立验证覆盖和截止，共享公共语义定义。边界脚本是复核证据。 [S12](Supplementary_Materials/S12_BINARY64_AND_COVERAGE_PROOF.md) |
| M6 | `ACCEPT` | §6.7 表 6 对 1,248 条归档方法—查询记录按预算分开列验证、进公共池、提案、达成及可提供结果的分母。保留 784 全、418 部分、46 无输出及同查询复用。 | 无输出不作为协议失败。排序、公共可行、提案和接受分开。相同前缀的回放一致只支持接入一致性。 [S11](Supplementary_Materials/S11_protocol_replay/README.md) |
| B1 | `ACCEPT` | 修正原 [24] 的出版者解析，输出 `Society for Industrial and Applied Mathematics (SIAM)`。统一保护正式书刊及会议名称，新增引文后编号按出现次序更新。 | 实际导出检查文字及 DOI。 [SIAM 官方书目](https://epubs.siam.org/doi/book/10.1137/1.9780898718027) |
| B2 | `ACCEPT` | §3 开头说明 V1–V5 和两条决策边界。§4 前解释签名、排序键、见证、K 和验证预算 B。 | K=500 是排序前缀检查点，提案次数单列。 |
| B3 | `ACCEPT` | 图 2、3、5 以原点位重绘，加大印刷字号，以共享图例减少图内遮挡。正文改用 S 编号，提交材料目录内有数据、索引和 SHA-256。 | 邮件单收 Word 依正文编号仍能定位附件，凸显图表的开发范围。 [补充材料索引](Supplementary_Materials/README.md) |
| B4 | `PARTIALLY_ACCEPT` | 采纳对确定 PDF 和 Word 的实渲染视觉核查。排版引擎、字体导致的页数差未被视为文本缺失。核对可编辑数学、每张表和六幅图。 | 论文 PDF 作为固定分页参考，Word 用于导师批注，页数可随本机引擎变化。 [交付复核](ROUND3_FINAL_QUALITY_AUDIT.md) |
