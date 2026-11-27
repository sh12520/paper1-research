# 引用核对与可用范围 / 2026-10-23

目的：为本轮首稿核对既有最近邻来源，不重新扩展研究主题。只采用规范、作者全文和机构书目。网页此次读取未在本目录封存原字节，不编造下载哈希。Google Scholar定向检索未取得可用的独立匹配记录；不据此判断文献不存在，也不填造引用次数/BibTeX。作者全文/正式规范/机构记录足以支持下列有限事实；最终投稿书目仍需逐项编辑。

| 编号 | 来源与本轮实际核对位置 | 首稿允许支持的事实 | 局限 |
|---|---|---|---|
| R1 | C. Bormann等，*GeneRic Autonomic Signaling Protocol (GRASP)*，RFC 8990，2021，[正式规范](https://www.rfc-editor.org/rfc/rfc8990.html)，§2.10.4 | GRASP不提供应用事务完整性，ASA须承担资源事务责任 | 不推出加事务后的ASA不可能满足RDINP核心；不是裸GRASP与SQLite耗时竞赛 |
| R2 | B. Carpenter等，*Guidelines for Autonomic Service Agents*，RFC 9222，2022，[正式文档](https://www.rfc-editor.org/rfc/rfc9222.html)，Appendix A，稳定存储段 | 资源池稳定存储属于已有义务，例示伪代码未包含完整稳定存储/崩溃恢复逻辑 | Informational，非新协议标准；伪代码缺省不等于原则不可实现 |
| R3 | Collin Lee、Seo Jin Park、Ankita Kejriwal、Satoshi Matsushita、John Ousterhout，*Implementing Linearizability at Large Scale and Low Latency*，SOSP 2015，[作者全文](https://web.stanford.edu/~ouster/cgi-bin/papers/rifl.pdf)，§3–4，PDF第3/5页（1-based）；[DOI](https://doi.org/10.1145/2815400.2815416) | 完成记录与操作效果应原子持久化，重试须定位已有记录 | RIFL不是单SQLite方案，不能拿其全系统开销作同配置对照；其client/GC lease不等于本项目资源lease |
| R4 | Jayant R. Haritsa、Krithi Ramamritham、Ramesh Gupta，*The PROMPT Real-Time Commit Protocol*，[作者稿全文](https://www.cse.iitb.ac.in/~krithi/papers/prompt.pdf)，§IV–V，PDF第4–6页（1-based） | deadline须绑定具体事件；该文定义基于master持久commit决定，prepared cohort后来仍执行决定 | 作者稿页首为期刊占位信息；机构书目入口此次403，不在首稿猜出版页码/DOI；未逐行重验其全部证明 |
| R5 | P. R. D'Argenio等，*Modeling and Verifying a Bounded Retransmission Protocol*，[Twente机构记录](https://research.utwente.nl/en/publications/modeling-and-verifying-a-bounded-retransmission-protocol)，1996；关联CTIT 96-22 | 有限重传不保证最终交付，协议可abort；已有SPIN/UPPAAL服务/协议核查 | [作者/机构PDF](https://www-i2.moves.rwth-aachen.de/i2/pdfs/181.pdf)此次两次访问超时；本轮仅用机构摘要支持这两个事实。历史全文审查见旧NOVELTY报告，不冒充本轮重读全文；不同报告/会议版作者顺序、页数不混填 |
| R6 | A2A项目，*Agent2Agent (A2A) Protocol Specification*，[固定commit全文](https://raw.githubusercontent.com/a2aproject/A2A/3303592588e388e62e0f69f701af531d2f4e3991/docs/specification.md)，§3.1.5、§3.3.1 | Send Message幂等为MAY，任务取消不保证成功；任务交互规范不等同于特定资源持久效果合同 | 本轮读取标头为Latest Released Version 1.0.0；旧报告称v1.0.1，二者不一致。首稿仅以commit标识，不声称“最新A2A”或修改旧报告 |

## TAC及其他文献的处理

Timed Atomic Commitment（1991）在旧审查中只取得书目信息/摘要，正文缺口仍存在，见[旧来源审查 S1](../rdinp-paper-final-audit-20261009/NOVELTY-FINAL-AUDIT.md)。本轮不反复尝试失效入口，不从PROMPT对它的二手介绍推断其完整性质；不把它列成已读全文，也不以其缺失证明本项目首创。

Agent Contracts、A2CN等更广比较保留在旧NOVELTY矩阵，本稿不依赖其精确算法/版本或优先权判断，不添加未经核对的性能数字。没有对“近两年所有协议”作穷尽声称；选取成熟近邻是为了避免将已知事务和ARQ原则重新包装。

## 与主张的边界

原子持久效果、幂等、未知结果和有限重传均有成熟近邻。本文的方法候选是这些义务在特定合同/事件/SQLite/保存证据中的可核对细化及其边界案例；现有文献核查不足以建立“首次联合”或强理论原创。全文缺失与投稿书目格式是引用限制，不自动授权新实验或协议变更。
