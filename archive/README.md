# 论文 1 研究档案

此目录收录原始材料的逐字节副本。可独立运行的示例和协作入口在仓库根目录的 [RDINP](../rdinp/) 和 [CS-ODS](../csods/)。

按研究阶段和用途查阅时，从[全局目录](../docs/research-index.md)进入。核对某条结论时，优先用[关键证据索引](../docs/evidence-index.md)定位报告与原始记录。

| 目录 | 内容 |
| --- | --- |
| [`genspace/`](genspace/) | GENSPACE-FAIL-01 研究源码、预注册材料、诊断与方法开发报告、论文稿件、已完成的 PILOT 与其他开发实验记录 |
| [`reorch/`](reorch/) | 运行期协商分组方向的源码、结果表和图 |
| [`rdinp-history/`](rdinp-history/) | RDINP 历史阶段的交付说明、验证记录和证据摘要 |
| [`v2x-development/`](v2x-development/) | OPV2V 通信计算敏感性与队列诊断，含逐帧和配对任务记录 |

[DIRECTORY_INDEX.tsv](DIRECTORY_INDEX.tsv) 按目录列出归档文件数量和大小。当前共有 34 行。各行互斥，可加总。`direct` 只统计该目录直属文件，`recursive` 统计该目录及其子目录。与当前清单的同步状态可用 `python tools/research_archive_index.py` 从仓库根目录检查。

[MANIFEST.tsv](MANIFEST.tsv) 记录原样收录的 18,790 份文件及 SHA256，共 700,270,516 字节。[archive_inventory.json](archive_inventory.json) 给出按方向汇总的文件体量。原始项目仍可用于复核依赖机器路径或额外资产的历史运行。

PILOT、DG-PCE V1 和论文开发比较三批结果占其中 16,065 份。初始导入在本机的 Git pack 约 46 MiB。历史文档可能引用原机路径或未随档案复制的中间文件。

原始凭证、实验令牌、未启用的持出确认材料、第三方可执行依赖、大型压缩包、环境目录和渲染缓存留在本地。已归档的开发结果保留其原有证据阶段和结论。