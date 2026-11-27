# METHOD HOLDOUT ROUTE · 准备态

**身份、准入、绑定核对通过。** 本轮启用准备态命名空间 `GENSPACE-METHOD-HOLDOUT-V1` 的原生持出入口。实际授权保持 `METHOD_HOLDOUT=false`，旧 `CONFIRM=false`。运行器接收独立发布者封存的序列化输入，未调用采样器。 [持出入口](results/method_holdout_readiness/holdout_runner.py) · [授权状态](METHOD_AUTHORIZATION_STATE.json)

## 身份与配对

配置域逐字段核对冻结 benchmark。按 family、pressure、conflict、richness、原深度及序号升序生成 **2,880 个基础身份**，每配置 30 个序号标签。**480 个 Depth 3 派生身份**取原深度 2 全部 48 个配置的标签 00–09，各冲突档 240 个；派生只增加查询身份后缀、将有效搜索深度置 3，引用原序列化字节。主终点 A 的 720 个槽由 rich 和原深度 2 固定。选择函数只读配置和序号，未读取候选表现、协议或 O1。全部 **35,520 个查询×方法键**不重复，轮换顺序可重建。 [身份计划](METHOD_HOLDOUT_IDENTITY_PLAN_DRAFT.json) · [测试](results/method_holdout_readiness/check_holdout_route.py)

发布清单须由实验授权绑定，包含全部基础身份及其唯一序列化 SHA-256、instance/public/private hash。读取路径限制在专用 release 根，同一文档被原深度及派生槽调用；外部路径、旧命名空间、字节、配置、模型、注册表或私有字段不符会拒绝。所有方法接收相同基础字节。工程测试在同一既有序列化实例验证了重复读取、原签名与改字节拒绝；新命名空间下尚无实际实例。 [准入实现](results/method_holdout_readiness/holdout_route.py)

## Gate 次序和实测

入口验证命名空间、可执行快照 envelope／锁定解释器、授权、方法／基线／依赖／资产哈希、配置与模型和注册表、身份计划、资源预算。授权以前不打开发布或结果根。通过授权后才要求配套 readiness 与独立 release 摘要。旧 PILOT 回执仅用于读取已发布的图资产来源，旧 PILOT 实例或封存排名不属于正式入口。

| 检查 | 准备态结果 |
|---|---|
| 真实 CLI、当前授权 | `AUTHORIZATION_DENIED`，退出码 2。 |
| 旧 namespace | SMOKE、PILOT、ENGINEERING、SHADOW、原 CONFIRM 和旧持出草案名称均拒绝。 |
| 禁用路径的种子、实例生成及打开 release | 监测调用数均为 0，正式输出根未创建。 |
| 配置、源码、依赖及图资产 | 候选源码和资产清单逐字节通过，准备快照可复核。 |
| 篡改快照、错绑授权、缺失独立发布和 readiness 审批 | 拒绝。测试篡改仅发生在新阶段临时文件。 |

5/5 个准入测试通过。序号仅是身份规划标签，本轮未产生随机映射、样本或 seed。未来独立发布及人工批准继续由该专用边界控制。 [执行快照草稿](METHOD_EXECUTION_SNAPSHOT_DRAFT.json)
