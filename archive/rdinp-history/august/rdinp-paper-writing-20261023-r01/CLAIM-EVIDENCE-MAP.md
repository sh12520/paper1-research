# 首稿主张—证据—限制映射

2026-10-23；本轮只读写作。`D5` 指 `../rdinp-d5-local-evaluation-20261023/`；`C2` 指 `../rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/`。本文的相对链接是实际来源，不以报告摘要代替全部原件。

## 可进入首稿的主张

| ID / 首稿位置 | 精确主张及强度 | 依据 | 不能推出什么 |
|---|---|---|---|
| M1 / §1、4 | 提供时间—租约—效果知识合同及事件/持久效果关联方法；ENGINEERING_INTEGRATION，方法价值仍待外部评价 | [C2合同 C1–C6](../rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/CONTRACT.md)、[D4限定映射](../rdinp-d5-local-evaluation-20261023/D4-CLOSURE.md)、[共同Π](../rdinp-d5-local-evaluation-20261023/PI-REFINEMENT.md) | 首个智能体资源合同；已优于其他审计方法；已证明易用性 |
| M2 / §5.1 | 诚实原子逻辑状态机中不超保护容量、同key不双重首提交；PROVEN_ABSTRACT，代码仅CONDITIONAL/TESTED_ONLY | [C2证明 S1/S2](../rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/CONDITIONAL-PROOF.md)、[独立理论审查 §6](../rdinp-paper-final-audit-20261009/THEOREM-INDEPENDENT-REVIEW.md)、[D5保存复核](../rdinp-d5-local-evaluation-20261023/reviews/20261023T055804Z-full-039790.json) | 物理CPU/带宽安全、多权威原子性、拜占庭或任意程序路径证明 |
| M3 / §5.2 | 在N=K等明示模型内有K计数及H充分上界；CONDITIONAL；计数紧界非协议最优 | [D4-CLOSURE §2](../rdinp-d5-local-evaluation-20261023/D4-CLOSURE.md)、[独立审查 §1/3](../rdinp-paper-final-audit-20261009/THEOREM-INDEPENDENT-REVIEW.md)、[既有有限模型结果](../rdinp-d5-local-evaluation-20261023/model-result.json) | N≥K普遍H；丢包率推出burst；C对任意负载恒定；全局最优 |
| M4 / §5.3–5.5 | I/H/d/V、失败发布及strict-tail组成保守充分条件；CONDITIONAL | [D4-CLOSURE](../rdinp-d5-local-evaluation-20261023/D4-CLOSURE.md)、[既有profile算术实现](../rdinp-d5-local-evaluation-20261023/profile.py)、[原证明及已披露勘误](../rdinp-paper-final-audit-20261009/THEOREM-INDEPENDENT-REVIEW.md) | 实际可行域、必要条件、硬WCET、任意中断按时终止；以旧冻结T1/T2量词覆盖勘误 |
| M5 / §3、5.6、7.2 | 请求丢失与提交后回复丢失可同为UNKNOWN；已纳入的真实COMMITTED证据不因确认失败退化 | [C2 K1](../rdinp-a1-candidate-2-20261008/runs/20261008T122605Z-5d47e005/source/CONDITIONAL-PROOF.md)、[Π](../rdinp-d5-local-evaluation-20261023/PI-REFINEMENT.md)、[105行原指标](../rdinp-d5-local-evaluation-20261023/analysis-output/metrics.csv) | 新知识理论；在线闭合全部UNKNOWN；terminal之后吸收所有迟到证据 |
| M6 / §6、7 | 三模式确有本地HTTP/JSON/JWS/SQLite链；B4为冻结C2字节副本，B2/B3为隔离policy变体 | [SOURCE-AUDIT](../rdinp-d5-local-evaluation-20261023/SOURCE-AUDIT.json)、[精确diff](../rdinp-d5-local-evaluation-20261023/EXACT-BASELINE-DIFF.patch)、[主run回执](../rdinp-d5-local-evaluation-20261023/runs/20261023T055804Z-full-039790/run-receipt.json)及同目录execution记录 | B2/B3通过C2全trace/wire conformance；换版或重新A接受 |
| M7 / §7.1 | 105主fixtures中103断言/严格复核通过，2失败保留；TESTED_ONLY | [独立review passed/failed/failures](../rdinp-d5-local-evaluation-20261023/reviews/20261023T055804Z-full-039790.json)、[失败取证](../rdinp-d5-local-evaluation-20261023/reviews/20261023T055804Z-full-039790-failure-forensics.json) | 98.1%网络可靠率、全105安全性/时限PASS、把前提违例更名为成功 |
| M8 / §7.3 | 两个意外初始化失败I=163.805/124.2865ms>100ms，零发送/零提交；有限安全拒绝观察 | [失败取证两条classifications](../rdinp-d5-local-evaluation-20261023/reviews/20261023T055804Z-full-039790-failure-forensics.json)及其cases路径 | 普遍fail-closed证明；安全拒绝等于成功活性 |
| M9 / §7.3 | 73fixtures/170个winning-path C超120ms；6个STRICT_TAIL含3个意外超50ms | [统计原件](../rdinp-d5-local-evaluation-20261023/analysis-output/statistics.json)、[全部metrics](../rdinp-d5-local-evaluation-20261023/analysis-output/metrics.csv)、[已有报告 §4.2](../rdinp-d5-local-evaluation-20261023/2026-10-23--rdinp-d5--r01--evaluation-report.md) | 全部170已被运行时拒绝；未超界paths已资格；这些样本出现过期后持久提交；在模型内反驳条件蕴含 |
| M10 / §7.4 | clean各12完整保留，消息mean±sample SD为15±2、18.167±7.056、27±9.085；描述性 | [statistics.clean](../rdinp-d5-local-evaluation-20261023/analysis-output/statistics.json)、[统计口径](../rdinp-d5-local-evaluation-20261023/analysis-output/stats-appendix.md) | 均值即单位成功服务效率；总体性能排名、因果或显著性 |
| M11 / §4.4、8 | B2/B3在Π下可承载同类核心义务；B4附加witness/确认为政策，有限证据未证明核心独有优势 | [人工弱模拟说明](../rdinp-d5-local-evaluation-20261023/PI-REFINEMENT.md)、[补充review](../rdinp-d5-local-evaluation-20261023/reviews/20261023T055804Z-full-039790-supplementary.json) | 全程序双向等价、全时序等价、B4无任何应用价值、确认机制普遍无用 |
| M12 / §6.3 | 独立算法能在保存副本负控制中拒绝重复提交/晚winner/知识倒退；TESTED_ONLY | [review negativeControls](../rdinp-d5-local-evaluation-20261023/reviews/20261023T055804Z-full-039790.json) | 全部缺陷可检出、false-positive/negative率、第三方认证、观察者开销已消除 |

## 三类贡献的准确表述

- C1：显式跨层合同及事件细化。组合/工程方法，不是新的原子性、exactly-once或ARQ原理。
- C2：受限充分条件及反例驱动的适用域说明。人工组合论证，不是新最优性定理。
- C3：跨三机制、保留负结果的来源绑定评价工件。迁移到同族变体有有限实证，不等于外部独立复现或优于现有工具。

## 必须删除或改写的表述

“保证协议完备”“首次联合合同”“四阶段必需”“N≥K即满足旧H”“已实现6G通信—计算联合优化”“本地实测认证硬界”“105全部通过”“已达到论文录用条件”均不可写。研究主线是可审计的条件与边界，而非这些未成立的主张。
