# 论文 1 研究档案

这里保留云端可查的历史报告、源码、汇总、图表和与主线有关的实证材料。按问题和阶段从[全局目录](../docs/research-index.md)进入，按结论从[关键证据索引](../docs/evidence-index.md)下钻。

| 目录 | 当前可查内容 |
| --- | --- |
| [`genspace/`](genspace/) | GENSPACE 研究方案、诊断报告、论文稿件，以及 PILOT、方法开发和 Depth 3 的摘要与关键对照表 |
| [`reorch/`](reorch/) | 动态分组方向的源码、判定报告、配对统计与图表 |
| [`rdinp-history/`](rdinp-history/) | RDINP 历史阶段的交付说明和验证摘要 |
| [`v2x-development/`](v2x-development/) | OPV2V 通信计算敏感性、配对结果和队列诊断 |

[DIRECTORY_INDEX.tsv](DIRECTORY_INDEX.tsv) 按互斥目录列出云端收录数量和原始字节。`direct` 统计直属材料，`recursive` 包括子目录。[MANIFEST.tsv](MANIFEST.tsv) 记录云端历史原件的相对路径、大小和 SHA-256。[archive_inventory.json](archive_inventory.json) 给出总量。运行 `python tools/research_archive_index.py` 可核对目录索引与清单是否一致。

## 本地原始结果

PILOT 大型逐实例表、序列化实例、逐次交易与遥测，DG-PCE 的多批逐例运行，语法搜索的逐查询明细，以及 REORCH 的完整原始运行表，已按原仓库路径移交本地。每批文件数和字节数见 [LOCAL_ARCHIVE_INDEX.tsv](LOCAL_ARCHIVE_INDEX.tsv)。

本机入口位于 `论文1/本地资料/历史交接/论文1_历史原始结果_666a39fa/`。其中 `LOCAL_FILES.tsv` 可按原路径查 SHA-256；`original_manifest/` 保存整理前的完整归档清单。所有移出的原文件均已在本地副本中逐项核验 SHA-256。

原报告中的路径按当时的目录保存。遇到已迁出的结果，先从本地目录取原件。具有 Git 历史时也可用 `git show 666a39fac685d0576849de7776a0c35d70d83e7f:归档原路径` 查看。发布标识 `666a39fa` 对应整理前的快照。

现行 RDINP 的 [论文、图表与原版复现包](../docs/proposals/README.md)、前期执行证据以及 5G-LENA 前传轨迹继续由当前仓库提供。
