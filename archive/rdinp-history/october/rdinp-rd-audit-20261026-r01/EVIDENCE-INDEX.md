# 审计证据索引

2026-10-26；所有程序检查均为读取既有字节/历史日志；没有重新运行RDINP。

## 核验结果

- 冻结27文件与原identity.source逐项匹配；重新计算sourceSnapshotId与记录一致：`sha256:ac7e4de2cf4ff537ae38db1ad3df79863bac1b29274be741f2b59ca662288b0d`。
- 最新交付的27份C2源码与该冻结source相同；读取保存stderr为52方法、exitCode=0，没有重跑。
- 接管开始所记1555份受保护输入前后哈希相同；另316份历史分析输入在分析读入及结束复核间相同。两组存在重叠，不能相加为不重复文件数。
- 这些结论仅适用于索引文件，不认证整个仓库、时间界或老师验收。
- [机器核验](./READONLY-VERIFICATION.json)；[重算汇总](./evidence/HISTORICAL-TIMING-RECOMPUTE.json)；[winning paths](./evidence/winner-paths.csv)；[tail paths](./evidence/tail-paths.csv)；[d/V区间](./evidence/transition-publication.csv)。
- [分析脚本](./evidence/historical_timing.py)只读标准库解析，运行需原D5目录；它不是新的协议实验或可迁移运行包。
## 规则与范围

本轮以用户最新“只读审计和方案设计”覆盖旧自主研发循环/投稿排版流程；没有写新task_contract、执行指令或新线协议revision。
读取research-ideation的5W1H/可证伪研究问题方法及原6g-paper-audit检查；本报告不是对新稿执行投稿评分。
当前规则字节凭证：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| [AGENTS.md](<C:/Users/16043/Documents/ChatGPT/GPT-协议/AGENTS.md>) | 2502 | `9193147b4c2271bf0146c6b02aba868c267e6a980782026b939d174d5b8edcd8` |
| [AGENTS.md](<C:/Users/16043/WorkBuddy/协议/AGENTS.md>) | 12619 | `ed5bf52f8d7bc478d91d8aae9ceb059604a709af2b179f3d722f1a3cc12683e2` |
| [AGENTS.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/AGENTS.md>) | 3698 | `c66b5b435ceed05114c590ee894e34d0692395ee890204390b8196f24dced562` |
| [SKILL.md](<C:/Users/16043/.codex/skills/research-ideation/SKILL.md>) | 8557 | `1f69e10a220c9d5feae688187ad4293d24d2e3c7e4804b9847d603846618fb17` |
| [SKILL.md](<C:/Users/16043/WorkBuddy/协议/skills/6g-paper-audit/SKILL.md>) | 8592 | `58208bb8df669a92d49b7c6e7b3826a26880f63b14236429aa3670a56ad2c6ca` |
| [reject-checklist.md](<C:/Users/16043/WorkBuddy/协议/skills/6g-paper-audit/references/reject-checklist.md>) | 7552 | `bf679230a6508798b9d4a8447e2bb6f4753a184e35d73f9742de4e8318d73aa1` |

## 关键证据入口

下列行号指未改原文件。完整阅读核心27文件，原始日志全部解析；并未声称逐字读取全仓每个归档对象。

| ID | 文件/定位 | 支持的判断 |
|---|---|---|
| E01 | [02_RDINP协议完整版.md:128](<C:/Users/16043/Documents/Codex/2026-10-24/6g-6g-16-1-intent-based/outputs/rdinp-advisor-final-delivery-20261026-r01/deliverables/RDINP_提交老师_20261026/02_RDINP协议完整版.md:128>) | 17章现行说明；四阶段、时间域、15项残余 |
| E02 | [PACKAGE-RECEIPT.json](<C:/Users/16043/Documents/Codex/2026-10-24/6g-6g-16-1-intent-based/outputs/rdinp-advisor-final-delivery-20261026-r01/PACKAGE-RECEIPT.json>) | 10月26日文档封包、newProtocolRuns=0、protocolCodeChanged=false |
| E03 | [contracts.py:80](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/contracts.py:80>) | N≥K、旧H与K位置lease可行性；104起cutoff；114实际attempt cap |
| E04 | [contracts.schema.json:300](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/contracts.schema.json:300>) | deadlineSafetyMargin的uint类型允许0（按字段检索核对行号） |
| E05 | [initiator.py:78](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/initiator.py:78>) | 先保留效果知识，再竞争/保存winner；terminal之后仅审计 |
| E06 | [initiator.py:128](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/initiator.py:128>) | 终态持久化、queue publication及事后超界记录 |
| E07 | [initiator.py:159](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/initiator.py:159>) | immutable start、I预算、write-ahead、phase origin、重试 |
| E08 | [authority.py:78](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/authority.py:78>) | 同事务处理/日志/commit及UNKNOWN，tail监测 |
| E09 | [authority.py:110](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/authority.py:110>) | 不可变units、receipt重放、first-effect guard、scalar admission |
| E10 | [authority.py:139](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/authority.py:139>) | strict-tail检查到全部durable-return；cleanup只释放暂存 |
| E11 | [endpoint.py:27](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/endpoint.py:27>) | 两POST、本地HTTP、hook位置；线程处理与响应生成 |
| E12 | [events.py:27](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/events.py:27>) | 逐条同步Trace的文件开关及观察时间区别 |
| E13 | [test_candidate.py:161](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/test_candidate.py:161>) | 旧attempt、丢失、知识、崩溃负例；283起有限计数检查 |
| E14 | [test_minimal_fixes.py:1](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/test_minimal_fixes.py:1>) | 13项A-B01/A-B02增量方法与边界 |
| E15 | [review_saved_run.py:126](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/review_saved_run.py:126>) | 离线事件/效果检查及负控制，非活性证明 |
| E16 | [THEOREM-INDEPENDENT-REVIEW.md:5](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-paper-final-audit-20261009/THEOREM-INDEPENDENT-REVIEW.md:5>) | 合法N>K反例、零margin等号、lease保守性 |
| E17 | [D4-CLOSURE.md:1](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/D4-CLOSURE.md:1>) | 受限N=K、正margin、事件锚点和限定条件 |
| E18 | [profile.py:1](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/profile.py:1>) | 受限算术资格检查及replay lookup，不是运行资格 |
| E19 | [PI-REFINEMENT.md:1](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/PI-REFINEMENT.md:1>) | 共同资源核心与B2/B3/B4政策区别 |
| E20 | [metrics.csv:1](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/analysis-output/metrics.csv:1>) | 完整105fixture指标与2失败 |
| E21 | [review_saved.py:185](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/review_saved.py:185>) | 原winning C诊断按scheduledNs到upper计算 |
| E22 | [PAPER-DRAFT-ZH.md:97](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-paper-writing-20261023-r01/PAPER-DRAFT-ZH.md:97>) | 实际论文r01§5.2反例、§5.5保守域、§7/8证据与局限 |
| E23 | [CLAIM-EVIDENCE-MAP.md:1](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-paper-writing-20261023-r01/CLAIM-EVIDENCE-MAP.md:1>) | 主张、证据及不能外推事项 |
| E24 | [07_版本与已知限制.md:5](<C:/Users/16043/Documents/Codex/2026-10-24/6g-6g-16-1-intent-based/outputs/rdinp-advisor-final-delivery-20261026-r01/deliverables/RDINP_提交老师_20261026/07_版本与已知限制.md:5>) | 15项原严重度、交付处理及研发残余 |
| E25 | [AUDIT-REPORT-ZH.md:167](<C:/Users/16043/Documents/Codex/2026-10-24/6g-6g-16-1-intent-based/outputs/rdinp-external-audit-20261025-r01/AUDIT-REPORT-ZH.md:167>) | 原6CRITICAL/8MAJOR/1MINOR逐项发现 |

## 主要历史验证/对照报告

- [2026-10-23--rdinp-baseline-optimization--r01--evaluation-report.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-baseline-optimization-20261023-r01/2026-10-23--rdinp-baseline-optimization--r01--evaluation-report.md>)
- [2026-10-23--rdinp-external-baselines--r01--reproduction-report.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-external-baseline-reproduction-20261023-r01/2026-10-23--rdinp-external-baselines--r01--reproduction-report.md>)
- [2026-10-23--rdinp-external-pi--r01--comparison-report.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-external-pi-comparison-20261023-r01/2026-10-23--rdinp-external-pi--r01--comparison-report.md>)
- [COMMON-CONTRACT.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-external-pi-comparison-20261023-r01/COMMON-CONTRACT.md>)

## 本轮新发现的直接日志位置

- [client.events.jsonl:12](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/runs/20261023T055804Z-full-039790/cases/000-clean-0-B2/client.events.jsonl:12>)：第一winner upper；同文件15行PERSISTED，下一COMMIT_INITIAL首SEND_SCHEDULED的scheduledNs作下一origin。
- [client.events.jsonl:83](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/runs/20261023T055804Z-full-039790/cases/001-clean-0-B4/client.events.jsonl:83>)：最终publication；与COMMIT_REPLAY winner upper比较108.3877ms。
- [server.events.jsonl:37](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/runs/20261023T055804Z-full-039790/cases/003-clean-1-B4/server.events.jsonl:37>)：final check，42行durable return，tail68.936ms。
- [server.events.jsonl:25](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/runs/20261023T055804Z-full-039790/cases/018-clean-6-B2/server.events.jsonl:25>)：final check，28行return，tail52.6151ms。
- [server.events.jsonl:21](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-d5-local-evaluation-20261023/runs/20261023T055804Z-full-039790/cases/051-late_response-1-B2/server.events.jsonl:21>)：final check，22行return，tail68.2422ms。

## 冻结27文件逐项读取/字节索引

完整阅读源码与文字规范；Schema逐项读取。以下“匹配”只指原identity里的字节pin。

| 文件 | 行数 | 字节 | 原身份匹配 |
|---|---:|---:|---|
| [audit_contract.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/audit_contract.py>) | 46 | 2943 | 是 |
| [audit_minimal_static.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/audit_minimal_static.py>) | 52 | 3928 | 是 |
| [authority.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/authority.py>) | 180 | 13705 | 是 |
| [CONDITIONAL-PROOF.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/CONDITIONAL-PROOF.md>) | 60 | 13020 | 是 |
| [CONTRACT.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/CONTRACT.md>) | 55 | 12863 | 是 |
| [contracts.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/contracts.py>) | 128 | 9045 | 是 |
| [contracts.schema.json](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/contracts.schema.json>) | 306 | 6327 | 是 |
| [crash_initiator.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/crash_initiator.py>) | 26 | 1449 | 是 |
| [crash_responder.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/crash_responder.py>) | 27 | 1234 | 是 |
| [crypto.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/crypto.py>) | 78 | 5103 | 是 |
| [endpoint.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/endpoint.py>) | 77 | 5370 | 是 |
| [events.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/events.py>) | 37 | 1607 | 是 |
| [initiator.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/initiator.py>) | 209 | 15274 | 是 |
| [local_demo.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/local_demo.py>) | 33 | 2127 | 是 |
| [message.schema.json](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/message.schema.json>) | 416 | 6563 | 是 |
| [openapi.json](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/openapi.json>) | 10 | 2457 | 是 |
| [requirements.txt](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/requirements.txt>) | 10 | 318 | 是 |
| [review_saved_run.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/review_saved_run.py>) | 225 | 19969 | 是 |
| [run_validation.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/run_validation.py>) | 43 | 3007 | 是 |
| [RUNBOOK.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/RUNBOOK.md>) | 35 | 3962 | 是 |
| [seal_candidate.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/seal_candidate.py>) | 58 | 4415 | 是 |
| [SIGNING-AND-PREIMAGES.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/SIGNING-AND-PREIMAGES.md>) | 31 | 7866 | 是 |
| [SOURCE-FILES.json](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/SOURCE-FILES.json>) | 32 | 641 | 是 |
| [TEST-PLAN.md](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/TEST-PLAN.md>) | 15 | 4121 | 是 |
| [test_candidate.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/test_candidate.py>) | 303 | 26926 | 是 |
| [test_minimal_fixes.py](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/test_minimal_fixes.py>) | 138 | 7635 | 是 |
| [trust.schema.json](<C:/Users/16043/Documents/Codex/2026-08-07/a2a-acp-adp-json-schema-6g/outputs/rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/trust.schema.json>) | 43 | 743 | 是 |

## 外部事实核验与限制

- A2A固定v1.0.0：官方规范§3.1.5、§3.3.1、§3.4；多轮关联、可选SendMessage幂等、尝试取消。本文未声称实现适配或已批准版本升级。
- RFC8990：官方§2.8.7/2.8.8及§2.10.4；已存在多步协商，事务完整性由ASA另保。
- ITU-R M.2160-0：读取官方建议书记录与框架信息；PDF全文本轮抓取未成功，没有引用具体数值KPI或声称全文核验。
- 未核实的论文全文、DOI、参数均不补写；16篇最近邻比较与Timed Atomic Commitment全文仍待补。
- PPT只抽取文字和备注；没有本轮视觉/字体/版式验收。旧验证结果是历史事实，不是本轮新通过。
