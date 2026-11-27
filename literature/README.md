# 论文 1 文献入口

从下表选一组阅读。稳定引用键在 [references.bib](references.bib)，共 13 条核心书目。既有论文稿的引用及历史 BibTeX 保留在原目录。

| 主题 | 优先条目与用途 |
| --- | --- |
| RDINP 协议与执行 | `sharma2023intentnegotiation` 是意图与替代方案基线。 `burrows2006chubby` §2.4、`lee2015rifl`、`rfc7252` §5.10.8.1 和 `rfc6241` §8.4 分别用于核对代际、持久请求结果、条件更新与确认提交。 [RDINP 历史文献审计](../archive/rdinp-history/august/rdinp-paper-writing-20261023-r01/REFERENCE-CHECK.md) |
| CS-ODS 方法与基线 | `mell2024optimal` 提供通用抽象最优合成先例，`kim2021semgus` 用于语义约束。Bee Search 与 Eco Search 是 best-first 研究对照。文献记录与实际复现范围见[关键证据](../docs/evidence-index.md)。 [Round 3 完整 BibTeX](../archive/genspace/PAPER1_ROUND3/PAPER1_REFERENCES.bib) |
| V2X 协同感知 | `hu2022where2comm`、`yang2023how2comm`、`zhu2026blindmap` 用于方法选择和版本核对，`xu2022opv2v` 用于基准数据来源。BlindMap 会版出版信息和作者公开代码已核，先保留论文时延分解为待查。 [文献与问题审查](../archive/genspace/AGENT_COMMUNICATION_PROBLEM_REVIEW.md) · [BlindMap 会版代码](https://github.com/AlexZhu2000/BlindMap) |

## 在三个工具之间查找

1. **Git** 保存可移植的书目、稳定引用键，以及研究结论所指向的证据。先在本目录按题目或 DOI 查，写论文时沿用已有键。
2. **Undermind** 用于发现文献与定位原文。现有工作区保留了需求失配检索和三个分类。论文键属于这个工作区。 [RDINP](https://app.undermind.ai/projects/5e79dc9b-5afe-43ce-bc7d-fa49e69b3341?path=/RDINP%20Protocol/) · [CS-ODS](https://app.undermind.ai/projects/5e79dc9b-5afe-43ce-bc7d-fa49e69b3341?path=/CS-ODS%20Synthesis/) · [V2X](https://app.undermind.ai/projects/5e79dc9b-5afe-43ce-bc7d-fa49e69b3341?path=/V2X%20Perception/)
3. **Zotero** 用于本机条目、附件和批注。Codex 的 Zotero 技能通过 `127.0.0.1:23119` 检查本机库。本机分类为「论文1 · 核心文献」，13 条已按题名、年份和可用 DOI 核对。其他电脑导入前，可先按 DOI 或题名查重，已有条目用分类复用。 [Zotero 本地 API](https://www.zotero.org/support/dev/web_api/v3/local_api)

| 仓库键 | Undermind 键 |
| --- | --- |
| `burrows2006chubby` · `lee2015rifl` · `sharma2023intentnegotiation` | `Bur06` · `Lee15` · `Sha23` |
| `mell2024optimal` · `kim2021semgus` · `ameen2023beesearch` · `matricon2025ecosearch` | `Mel24` · `Kim20` · `Ame23` · `Mat25` |
| `hu2022where2comm` · `xu2022opv2v` · `zhu2026blindmap` · `yang2023how2comm` | `Hu22` · `Xu21` · `Zhu26` · `Yan23e` |

Git 优先记录正式出版版。Undermind 的 `Xu21` 和 `Hu22` 指向 arXiv 索引，可用 arXiv ID 与 Git 的会版记录核对。SemGuS 的正式出版年按 POPL 2021 记录。RFC 使用 RFC Editor 的固定链接。

新增书目按 DOI、arXiv ID，再按规范化题名和作者核对。用于技术主张时另记原文节号、表或代码版本。仅查到元数据的条目可以导航，结论需要原文依据。Zotero 数据库、凭证、私人批注和第三方 PDF 通过各自的授权渠道管理，仓库只同步需要协作的资产。 [Zotero 多电脑使用说明](https://www.zotero.org/support/kb/using_multiple_computers)
