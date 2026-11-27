# D5 local evaluation / r01 / preregistration

2026-10-23 · 在新增 baseline 源码和运行结果产生前固定。授权：10-22 D4=A/D5=A 及本轮“继续工作到完成 d5”。只做一次隔离本地评价，无服务器/B/Release/多方/物理扩展。

## Questions and units

- RQ1：一个共同 Π oracle 能否跨 B2/B3/B4 检出冲突效果、超售、重复应用、身份/签名错配、非法 winner 和知识倒退，而不把额外确认政策写入核心安全？
- RQ2：真实本地 HTTP+JSON/JWS+SQLite 中，三者在相同输入/故障族下的效果、UNKNOWN、确认和逻辑消息/持久事务成本如何不同？
- RQ3：N=K 与 strict-time/lease 判定能否区分可引用域、边界等号、已知域外反例与前提违例？

主比较量为**正确性分类、逻辑请求/回复数与持久事务/选中 winner 数**；本机耗时仅描述性辅助，不作为实时/性能资格。clean 12 个重复块，bounded_loss/late_response 各 4 个块，块内 B2/B3/B4 顺序按固定种子 20261023 置换。种子控制执行顺序，不固定密码学私钥或 OS 调度。秘密钥仅内存；保存公开 pins、签名原文、输入、trace、SQLite、错误和结果。

## Common profile and fairness

使用 D4-CLOSURE §3 原 C2 fixture 数值；baseline 只按交换数缩短 phase 列表，截止/lease/R/C 等不加宽。独立研究版本号和 Schema 域；B4 必须是捕获 source 的字节相同副本（27 项）且保持原 revision。B2/B3 对应的精确差异/来源必须保存；不是新 C2 验收或 Release。

所有模式：相同 principals/静态 ES256 授权、integer JCS、业务 key、resource units/容量、SQLite FULL 同步、immutable start、non-retiring retry、durable winner、strict-tail、cleanup/boot、offline-only restart。Π 不要求 B4 的额外 witness；B4 政策结果单列。B3 第三交换为已授权比较方案的 receipt replay，不能首次生效，不是给冻结内核添加在线恢复。

## Finite execution inventory

常规对照：clean×12、每个阶段首请求及首生成回复各抑制一次 bounded_loss×4、首回复延迟 60ms（R=40<C=120）late_response×4。它们声明同一受限输入 profile，但**没有独立资格的真实成本/损失界**，观测超界必须披露。

边界/负例各一次、每模式同策略：capacity_reject、all_commit_requests_lost、all_commit_responses_lost、post_commit_read_loss、initial_over_budget、intent_clock_error、commit_clock_error、cutoff_equality、lease_tail_guard、expired_before_commit、tail_overrun、restart_history、duplicate_and_conflict、illegal_first_effect、capacity_race。共 35 fixture/mode、105 fixture；manual case 可以含多个同身份 negotiation，不增加第三主体。

对不含 post-commit read 的 B2，post_commit_read_loss 应记录 fault_not_applicable，不能篡改其 COMMIT 以凑故障；该项是政策对照，不计相同故障下性能优势。all_*_lost、时钟跳变/错误、尾段越界均为声明成功前提外的机制检查，不混入域内成功率。

另做有限组合模型/算术检查：q/r∈{0,1,2} 的 N=K 计数域、N<K 见证、已保存 N>K 回复重排反例、margin 等号和 B2/B3/B4 符号预算；上限 50000 状态/轨迹、单次 30s。模型结果只适用于模型，不冒充 HTTP 或真实网络。

## Independent oracle / analysis

独立复核不 import 各 baseline 的业务/验证代码：重新验证 JWS、raw/JCS request linkage、receipt→decision、SQLite 事务/效果与容量前缀、永久结果一致、唯一且严格 cutoff winner、write-ahead、publication 与知识；检查所有计划 fixture 的存在、exit 与 source pins。对保存副本作明确负控制（重复 COMMIT/非法 winner/知识倒退），必须拒绝。不得修改原结果。

统计：clean 的配对消息/事务计数报告全部点、mean/SD、范围和配对差；确定性精确计数无需 p 值。耗时报告 median/IQR 与全部样本；单机依赖且块数小，**不做总体优越性/硬界显著性推断**；CI/p-value 不适用的原因明确记录，不伪造统计资格。失败/超界不剔除；性能汇总按预定族分层，不能择优合并。生成至少两张真实科学图（SVG/PNG）并给数据/解释。

## Stops, resources and definition of done

首次进入隔离实现时登记 START 与 +56 日 deadline，不等运行成功才计时；最晚到时停止扩展。有限一次评价可提前完成，无需耗满八周。

初次计划 105 fixtures；如暴露 harness/baseline 普通缺陷，保留失败整轮，只做有因修复，最多两次完整修正运行及 30 次定向复测，总 fixture 上限 345，单子进程 25s，整批 30min，磁盘新增上限 250MB。触及限制则 checkpoint 报告，不擅自扩大；C2 新安全反例或必须改 G1–G6 立即停受影响分支报 Owner。

完成条件：D4 限定域记录；三模式真实本地端点；计划用例/失败全部有身份；共同 oracle +负控制；预算/计数边界；分析图表及局限；独立封存/来源一致性；精简 Owner 决策包。完成 D5 是完成这次评价，不是“所有结果必须 PASS”、协议最终完备、论文录用、A 新验收或 B 资格。
