# METHOD CONFIRMATION V1 · FINAL DRAFT

**准备态，等待人工批准及剩余闭合证据。** 独立命名空间 `GENSPACE-METHOD-HOLDOUT-V1`、快照及授权文件保持准备态。旧 9,600 实例与 Gate A–E 沿用原研究用途，本实验不访问其输入。

## 固定方案

- 原深度 96×30=2,880 个基础身份。主要 A 取 24 个 rich、原深度 2 配置各 30 个，共 720 对。主要 B 取 48 个原深度 2 配置各前 10 个，给同一基础记录设置方法有效深度 3，共 480 对。所有方法读取同一字节，选样与 O1、运行状态及方法结果无关。 [身份审计](METHOD_HOLDOUT_ROUTE_AUDIT.md)
- 主比较使用冻结的 `DepthCursor` 与确定性 MRV `GenericCursor`。原深度使用现有一至两机制组合同域，Depth 3 使用一至四机制组，候选身份、原 FLAT binary64 分数、排序、能力前置、exact verifier 与双边协议遵循冻结实现。A1–A6 同槽比较。Depth 3 三条图路线为 N/A。 [方法版本](METHOD_FREEZE_MANIFEST_FINAL_DRAFT.json)
- 原深度 K=10/50/100/500，Depth 3 K=10/100/500。共同墙钟 12/45 秒，工作集 2 GiB，native expansion 300,000/2,000,000，frontier 180,000/260,000。按固定阶段和轮换执行。父端监督比候选的内置计时更早建立截止边界，IPC 和父端停止时间另记。主要时延来自已独立认证的 K=500 暖态公共搜索时钟。B2、验证、协商重放、独立复核、冷启动与离线图／索引成本单列。 [资源计划](METHOD_HOLDOUT_RESOURCE_PLAN.md)

## 判定

| 终点 | 主要估计 | 判据 |
|---|---|---|
| A | 每个原深度 rich 查询的 `log(T*_generic / T*_current)`，配置内均值后 24 等权。T* 的认证时长最低 1 ms，获归属的未认证用 12 s 处罚。 | Bonferroni 单侧 97.5% 下界指数化后严格 >1.25。当前认证至少 684/720，认证数相对基线最多落后 14。 |
| B | 每个 Depth 3 查询的 `C_current − C_generic`，配置内均值后 48 等权。完整全长和已证穷尽短域均为 C=1。 | Bonferroni 单侧 97.5% 下界严格 >0.20。当前认证至少 456/480。 |

固定有界 Hoeffding 区间，两个主要判定各用单侧 α=0.025，另给每目标名义双侧 95% 区间。配置内重抽整对，维持两方法对应，再跨配置等权。确定性 bootstrap 仅作敏感性描述，门禁使用 Hoeffding 区间。正式计时独立性及漂移需预先审核。完整预定查询按状态留档，另列共同认证的条件化秒差、展开差与评分。可归属超限是未认证，`UNSOUND`、无证据和不可核清缺失触发阻断。历史开发数据用于实施核对。 [统计实施审计](METHOD_STATISTICS_IMPLEMENTATION_AUDIT.md)

## 证据与执行边界

原深度由已验证的独立 Full FLAT 新算参照审计位模式、规范键及顺序。Depth 3 必须有独立穷尽或可核验的全覆盖及下界证明，仅凭冻结搜索的最小 frontier 数不能宣布认证。运行器将缺证结果标记 BLOCKED。每条完成事务校验证书摘要、实例和版本后原子封存；恢复验证后跳过已提交项。人工批准、完整 rich Depth 3 证据和整条持出路径验收均在生成持出输入之前完成。 [证书复核](UNSEEN_CERTIFICATE_VERIFIER_AUDIT.md) · [监督恢复](METHOD_SUPERVISOR_RECOVERY_AUDIT.md)
