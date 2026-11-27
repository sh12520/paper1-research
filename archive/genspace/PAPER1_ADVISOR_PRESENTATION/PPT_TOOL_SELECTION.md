# 导师汇报工具选择

**选择本地 Artifact Tool 生成可编辑 PPTX，使用 Microsoft PowerPoint 16.0 导出 PDF，使用 Poppler 与 Pillow 制作和检查逐页预览。** 在正式排版之前，用本机探针生成一张带原生图表、中文文本和演讲者备注的 PPTX。PowerPoint 可以打开探针并导出 PDF，提取出的中文正常。

| 候选 | 本机发现与实际验证 | 选择 |
|---|---|---|
| Presentations Skill 与 `@oai/artifact-tool` | 技能和运行时 `26.1112.11011` 已加载。实际导出带文本、备注及图表的 PPTX。 | 用于正式制作。 |
| Microsoft PowerPoint 与渲染组件 | PowerPoint 16.0 COM 已实际打开探针并导出 PDF。Poppler 和 Pillow 可用。 | 用于真实 PPTX 渲染、PDF、PNG 和文本复核。 |
| PptxGenJS | 本机已捆绑 4.0.1，MIT。GitHub 快照约 6.4k stars，官方仓库有文档和范例。 | 保留为本地替代；当前 Artifact Tool 已满足制作需求。 [官方仓库](https://github.com/gitbrent/PptxGenJS) |
| python-pptx | 已确认模块存在。 | 本次用 OOXML 做结构检查，正文由专业演示工具生成。 |
| Mermaid | 官方仓库约 91.2k stars，MIT。运行时未发现独立包。 | 流程用 PowerPoint 原生文本、形状和连线，投影片内可以单独修改。 [官方仓库](https://github.com/mermaid-js/mermaid) |
| Canva、Presentations Craft | 连接器工具定义可见。未建立该项目的远程编辑会话。 | 采用本地工作区，直接输出指定路径，同时保留数据和备注。 |
| Spaces / Artifact Session、Google Slides | Artifact Session 工具可见，无绑定演示文稿。当前工具清单未发现本地交付所需的 Spaces 创建/连接入口或 Google Slides 原生 authoring 路线。 | 本任务交付独立本地 PPTX、PDF 和 PNG。 |
| Presenton | 技能文档和官方 GitHub 可核验。其公有导出流程需要外送幻灯片 HTML。 | 本次保留论文资料和图表在工作站，未调用远程导出。 [官方仓库](https://github.com/presenton/presenton) |
| 模板、图形资源、专用渲染 | 用户已给出具体学术风格。已确认本机 Microsoft YaHei 字体。 | 自建 16:9 版式，形状和学术图按证据绘制，外部装饰资产为零。 |

已具备稳定本地工具，未安装新依赖，未改动冻结科研环境。涉及 GitHub 的星标仅为核验时页面近似值。
