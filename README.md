# Paper 1 Research

Small, reproducible research examples for intent contracts and deadline-aware resource commitments. This repository brings together two research lines with distinct assumptions and evidence.

本仓库集中维护论文 1 的两个研究方向。近期主线是 RDINP 的限时资源承诺及服务履约验证。较早的 CS-ODS 是能力约束合同搜索方向。分别从对应子目录运行。

**从[论文 1 研究索引](docs/research-index.md)开始。** 索引按当前主线、关键证据和核验档案三层组织，附研究时间线。

| Path | Contents |
|---|---|
| [`rdinp/`](rdinp/) | RDINP control-plane reference, local protocol checks and execution-layer diagnostics |
| [`csods/`](csods/) | Graph-free semantic search within the bounded communication-contract DSL and reduced-domain checks |
| [`docs/research-map.md`](docs/research-map.md) | Research questions, evidence boundaries and preserved historical scope |
| [`archive/`](archive/) | 原始论文稿件、源码、已完成的开发实验结果及文件摘要 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Development and evidence practices for contributors |

Each subproject documents its own Python dependencies and run commands. Examples use small local fixtures. The private research archive includes selected original manuscripts, development data, result tables, and evidence. See the archive guide for coverage and local-only assets.

No redistribution license has been selected for this draft export. The project owner can add the appropriate terms before enabling public redistribution.
