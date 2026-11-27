---
type: results-report
date: 2026-10-23
experiment_line: rdinp-d5
round: 1
purpose: evaluation-report
status: completed-with-negative-results
source_artifacts:
  - analysis-output/analysis-report.md
  - analysis-output/stats-appendix.md
  - analysis-output/figure-catalog.md
  - reviews/20261023T055804Z-full-039790.json
linked_experiments:
  - PREREGISTRATION.md
linked_results:
  - analysis-output/statistics.json
---

# RDINP D5 / Round 1 / Evaluation Report / 2026-10-23

## 1. Executive summary

**本次有界 D5 评价已完成，但结果不是全 PASS，也不是协议最终完备/时间资格。**

- D4 评价前置以 N=K 的受限条件域关闭，独立反例/失败发布勘误保留；不修改冻结 C2。
- B2、B3、B4 均实际执行 loopback HTTP、JSON/JWS 验签、SQLite 原子事务与客户端状态；B4 为 C2 27 文件字节副本。
- 主运行 105 fixtures：原断言 103 通过、2 失败（均保留 exit=1）。独立严格保存复核同为 103/105；另外两项独立取证确认是初始 I 超预算且首发前安全拒绝，**没有改记为成功**。
- 更重要的负结果：73 个 fixture 有至少一个 winning-path C 超声明的 120ms，共 170 次；6 条 STRICT_TAIL 违例中 3 条不是故意延迟案例；这台机器没有满足/资格化所声明的统一时间前提。
- 在有限保存样本及明确模型中，简化 B2/B3 能提供核心 Π 的资源安全与效果知识；B4 的附加确认政策有可见成本，但未发现它带来额外核心资源安全保证的证据。
- 结论保持 **YELLOW/P1 系统方法候选**：可复用合同、独立 oracle 与边界负结果具有工件价值；不推荐包装成强原创提交理论或确定性 6G 保证。

## 2. Experiment identity and decision context

批准来源为 [10-22 Owner 明确回答](../rdinp-d4a-d5a-20261022/OWNER-AUTHORIZATION.md)及本轮“请继续……工作到完成 d5”。[D4-CLOSURE](D4-CLOSURE.md)只关闭 D5 的限定 profile 前置，未修订 C2 原文、G1–G6 或普遍配置能力。

时间盒：START.json 记录开始为 2026-10-23 13:48:10.851562 +08:00，八周上限为 2026-12-18 05:48:10.851562 UTC。八周是最长时间，不要求耗满；本次有限计划已执行，不自动续一轮。

| 身份 | 值 |
|---|---|
| 隔离评价 sourceSnapshotId | sha256:a836a621f96df2d042a63a5b776bcb993a60550ff6512969bb307318aee920ee |
| 主运行 | runs/20261023T055804Z-full-039790 |
| 主 runArtifactId | sha256:c89ea08403e3aaf579ba7bcd4dd61e925736db2f960fed6402e8d93c47367757 |
| 解释 | 本次 48 文件来源闭包包括 B4 27、B2/B3 各9、三个执行 helper；不是旧 C2 身份 |
| C2 accepted sourceSnapshotId（未变） | sha256:ac7e4de2cf4ff537ae38db1ad3df79863bac1b29274be741f2b59ca662288b0d |
| 根 Git HEAD | 17314674720f73482ff05f9452bd2a89ee486cdf；本轮没有 commit/push；旧 run.gitHead=null 不回填 |

source/run/archive 身份分开。归档身份见独立最终决策包与 archive-v1/RECEIPT.json，不将此表的 runArtifactId 当 archiveId。SOURCE-AUDIT.json 和 EXACT-BASELINE-DIFF.patch 记录原 C2 不变及 baseline 精确差异。

## 3. Setup and evaluation protocol

详见事前保存的 [PREREGISTRATION](PREREGISTRATION.md)。共同模型为双主体、单诚实 SQLite 逻辑池、同静态 ES256/JWS 与整数 JCS、同身份绑定/幂等、不续租、strict-tail、immutable start、non-retiring retry、durable winner、UNKNOWN/既知效果保持、离线恢复边界。不同策略见 [PI-REFINEMENT](PI-REFINEMENT.md)。

B2=Reserve→Commit；B3 增加只读已有 receipt 的第三交换；B4 保留四阶段、INTENT_REPLAY witness 及双观察政策。B2/B3 不是 C2 wire/full-trace conformance，不能对外当成已接受 RDINP 新版本。删除的是对应政策，不是鉴权/持久化/资源安全机制。

fixture 沿原示例：Ibar100ms、q=r1、N=K4、R40ms、C120ms、d20ms、V100ms、D_final5000ms、lease10s、tail50ms、margin1ms；没有因失败调大。常规 clean12、bounded_loss4、late_response4 块，各含三模式；15 种边界各三模式，共 105 fixtures。固定 seed20261023 控制块内顺序。秘密钥仅内存，保存公开 pins、签名原文、SQLite、fault actions、stdout/stderr/exit；没有真实网络注入或服务器操作。

smoke3、定向45 为单独的实施校验，均保存并独立复核通过；**不与主105合并成148/153项“统计成功”，更不加入旧52回归**。只有一次105完整计划运行，没有为了去掉两个失败重跑 clean。

## 4. Main findings

### 4.1 核心效果、知识和确认确实不同

| 场景（各模式一次） | B2 | B3 | B4 |
|---|---|---|---|
| COMMIT 请求全抑制 | UNKNOWN，commit=0 | 同左 | 同左 |
| COMMIT 回复全抑制 | UNKNOWN，commit=1 | 同左 | 同左 |
| 后提交 read 回复丢失 | COMMITTED，complete=true；无该额外阶段 | COMMITTED，complete=false | COMMITTED，complete=false |
| COMMIT private clock error | COMMITTED 知识保留，complete=false | 同左 | 同左 |
| COMMIT 前到期 | NOT_APPLIED，commit=0 | 同左 | 同左 |

抑制/时钟错误/跳变等是机制案例，不是满足有限损失/时钟前提的成功活性样本。post-commit-read 对 B2 不适用，故其 complete=true 不是“相同故障下 B2 更可靠”的证明。资源竞争/重复/非法首效果/重启保存历史也有实际本地样本，不是只有审计器模拟。

### 4.2 失败与时间前提是本次重要负结果

| clean 失败 | 观察 I | 声明预算 | 结果/证据 |
|---|---:|---:|---|
| B3，seed1 | 163.805ms | 100ms | ASSUMPTION_FAILURE；零发送、零效果、NO_COMMIT_SENT；exit=1保留 |
| B4，seed9 | 124.2865ms | 100ms | 同上；exit=1保留 |

见 [failure-forensics](reviews/20261023T055804Z-full-039790-failure-forensics.json)。这两项支持初始预算保护的有限行为，反驳“无故障本机运行必然满足初始化预算”的实用假定，不反驳以 I≤Ibar 为前提的抽象条件命题。

73 个 fixture 共170个 winning C 超声明；其中 clean36里32个至少有一次。这个数不是无线失败率；即使无超界记录也无法认证 losing paths 的成本。软件没有检查每个 C 超界，本轮独立审计才作该诊断，因此“客户端完成”不能当成条件模型被满足。

STRICT_TAIL 共6条：故意 tail_overrun 三条；非故意三条分别是 B4 clean/seed1=68.936ms、B2 clean/seed6=52.6151ms、B2 late_response/seed1=68.2422ms，超过50ms声明。它们实际 durable return 仍分别距 lease expiry 约9.147/9.488/9.438秒；**没有在这些样本中观察到过期后持久提交，但不能因此认证严格尾段上界**。真实 COMMITTED 效果全部保留，未伪造回滚。

INITIAL_BUDGET 共5条=故意 initial_over_budget 三条+上述意外两条。不得只展示故意违例而遗漏意外违例。

### 4.3 成本只作结果分层的本地描述

| mode | clean总数 | 已知COMMITTED计数 | 确认完成计数 | 原断言失败 | 消息记录 mean±SD（含拒绝） | 范围 |
|---|---:|---:|---:|---:|---:|---:|
| B2 | 12 | 12 | 12 | 0 | 15.000±2.000 | 10–16 |
| B3 | 12 | 11 | 11 | 1 | 18.167±7.056 | 0–24 |
| B4 | 12 | 11 | 11 | 1 | 27.000±9.085 | 0–32 |

同一块三模式都完成的10块，B4−B2 的 winner persists 每块多2，B3−B2多1；观测消息差平均分别14.4与4.8，但高度依赖本机重试/存储抖动，且该子集按结果选择，**不是因果或总体效率增益**。零发送拒绝会降低无条件消息均值却没有提供提交服务，不能按均值给协议排效率名次。

理想单 attempt 逻辑消息数4/6/8、充分发布预算700/960/1220ms是**符号预算/算术结果**，不是实测均值或“达到这些截止的资格”。现实 clean 由于重试常接近各自消息 cap16/24/32；固定 R/C 与实际主机不匹配，正是不能把 fixture 数值当合格界的证据。

## 5. Statistical validation

见 [analysis-output/stats-appendix.md](analysis-output/stats-appendix.md)、[全部105行 CSV](analysis-output/metrics.csv)、[statistics.json](analysis-output/statistics.json)。报告全部点、n、样本SD、median/IQR、原始配对差。没有独立网络/总体随机采样；同机调度相关，故不作 p 值、总体CI或硬界推断。检验正态性也不能修复独立性/结果选择问题。

有限组合计数实际执行11533对合法 stream、9个q/r配置、36个N<K见证，保留合法N>K重排反例和margin等号；[model-result.json](model-result.json)与独立脚本有限范围清楚。该数字与历史小计数模型相同，不把重复计算当成新理论成果，也不证明全程序。

严格保存复核不 import baseline 业务/验证实现，重做 JCS/JWS、request/response hash、decision/receipt、SQL效果前缀、唯一winner/upper、write-ahead及效果知识检查；三个内存负控制（重复 COMMIT、cutoff等号winner、知识倒退）均被拒绝。它是同一研究过程的独立算法，不是第三方认证。原两个 failed assertions 保持 failed，取证不是改审计器制造105 PASS。

## 6. Figure-by-figure interpretation

![Clean cost](analysis-output/figures/figure-01-clean-message-cost.png)

图1：36个clean原始点，红叉为保留的首发前拒绝；虚线只表示理想最小消息数。观察到大量重试以及附加政策的消息工作。它改变的认识是：不能把理论单交换成本当实测，更不能以拒绝零消息获得虚假效率优势。数据/矢量版/解释见 [figure-catalog](analysis-output/figure-catalog.md)。

![Knowledge vs confirmation](analysis-output/figures/figure-02-effect-vs-confirmation.png)

图2：每单元一个实际机制fixture，分别展示客户端知识、权威COMMIT计数和确认完成。UNKNOWN不决定真实效果；再次确认失败也不取消已知COMMITTED。它支持外层接口必须分层表达结果，而不支持“额外确认天然增加核心安全”或总体可靠率主张。

## 7. Failure cases / negative results / limitations

- 主运行与严格 review 均 exit1，两个失败保留，未换预算/删样本/重跑择优。
- 多个时间前提实测不满足；不新增硬实时、截止成功率、无线网络或 B 资格结论。
- 本轮是在同机完整日志/签名/SQLite 下测观察者相关开销，非裸协议吞吐；baseline 的真实 C 未证明相等。
- 不含真实端点、断电/介质故障、恶意权威、多方、物理执行或在线恢复。
- Π 不是 B4 全轨迹；额外 witness 的应用必要性仍未有独立场景证据。四阶段本身不是新安全性理论。
- 初步协议比较已核对的公开来源见上一轮 SOURCE-REGISTER；本轮不重新扩大文献/应用范围；论文新颖性仍须诚实对照历史近邻。

## 8. What changed our belief

1. 简化核心服务不只停在伪代码：已实际得到三模式可审计链和共同 oracle；但只是有限实现证据，不是泛化等价证明。
2. 初始化与整个持久提交尾段确实会在普通本机环境超声明，不能把负例仅当人工注入。合同能揭示前提不足，这是方法价值的有限证据。
3. B4 的政策完成与效果知识不是同一指标；继续追求“B4比B2普遍安全/快”没有证据基础。

## 9. Next actions / stop

本轮到此停止新增运行/增强，不开展第二轮或 B。建议 Owner 选择：以合同/证据/边界为主线进入 P1 写作，或者将其收为硕士系统模块；若未来需要性能/指定域 claim，另立最小域资格，不在本次偷偷追加。当前不需要为了完成 D5 而放宽 C2、G1–G6 或延长时间盒。

Owner 对 D5 研究结果的采纳仍 PENDING；C2 原受限A接受不变，Release=false、BQualified=false、finalGoalComplete=false。

## 10. Artifact and reproducibility index

- [PREREGISTRATION](PREREGISTRATION.md)、[D4-CLOSURE](D4-CLOSURE.md)、[PI-REFINEMENT](PI-REFINEMENT.md)、[START](START.json)。
- `modes/B4/`27原字节；`modes/B2/`、`modes/B3/`；[SOURCE-AUDIT](SOURCE-AUDIT.json)、[EXACT-DIFF](EXACT-BASELINE-DIFF.patch)。
- 主 run `runs/20261023T055804Z-full-039790/identity.json`、`planned-fixtures.json`、`execution-*.json`、`cases/`、`run-receipt.json`；失败不能忽略。
- [严格独立review](reviews/20261023T055804Z-full-039790.json)、[失败取证](reviews/20261023T055804Z-full-039790-failure-forensics.json)、`reviews/tools/`工具字节。
- `analysis-output/`分析、原数据表、两图；[有限模型](model-result.json)。归档/校验见最终决策包；新原始DB/trace仅本机，未进行Git/云端上传或Obsidian写回。
