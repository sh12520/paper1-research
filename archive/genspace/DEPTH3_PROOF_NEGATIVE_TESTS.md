# Depth 3 覆盖证明负对照

原始 `typed-cover-dag-v2` 裁判拒绝了 11/11 项负对照，符号化 `symbolic-typed-cover-dag-v2` 裁判也拒绝了 11/11 项。原始证明使用已封存的 `F4__high__high__sparse__d2__s0`。符号化证明使用 `F4__medium__high__sparse__d2__s0`，并复用前一个查询检验虚假的短域穷尽。两条路径均先独立接受对应的原始证明。符号化重放的候选键、binary64 分数和 witness 与这两个查询的封存前缀完全相同。

| 注入变更 | 原始证明的拒绝依据 | 符号化证明的拒绝依据 |
| --- | --- | --- |
| 删除合法子节点 | 独立重建的 constructor 分支数与证据不符 | 从根重建时缺少合法语法分支 |
| 遗漏参数分区 | 嵌套节点缺少一个 profile 选项 | 一个 frontier assignment 的 profile 掩码丢失一位，覆盖不全 |
| 提高剪枝下界 | 将原值提高一个 binary64 ULP，独立复核拒绝该 cutoff | 新报值大于重新计算的保守下界 |
| 错误能力掩码 | 声称的角色集合与固定公开输入不符 | 篡改后的公开 capability 绑定与预期绑定不符 |
| 错误语义合并 | 合并两个语义键不同的独立完成项时被拒绝，同一键的合并正对照通过 | 替换为全新内容寻址的模板后，独立重建的上下文模板集合中无该项 |
| 改动并列排序 | 互换一对 binary64 得分完全相同的候选，裁判按语义键发现第 2 名错序 | 同样的真实分数并列扰动，由独立前缀排序检查拒绝 |
| 删除前沿节点 | 保留仍引用被删除节点的边，裁判发现无效引用 | 删除整条 frontier assignment，独立核对发现缺少覆盖 |
| 截断证明文件 | JSON 解码失败 | JSON 解码失败 |
| 修改 query fingerprint | 公开输入绑定不符 | 公开输入绑定不符 |
| 虚报短域穷尽 | 从 81 个语义合同的穷尽结果删除最后一项，语义前缀复核失败 | 从同一穷尽结果删除最后一项，核对发现尚有合法 assignment |
| 将旧 snapshot 证明用于另一查询 | 重绑新查询及候选前缀后，旧 snapshot 仍不匹配 | 重绑新查询后，旧 snapshot 仍不匹配 |

重新序列化每个可解析的变更，并记录新的 SHA256。符号化证明中改变节点内容时同步重新计算节点的内容标识，并裁去已无引用的记录。两种虚假穷尽测试均调整声称的合同数、cutoff 边界和前缀摘要，因此裁判须实际核对候选与覆盖。并列测试允许裁判收到内部一致的改动前缀，拒绝依据是独立排序检查。

测试仅使用既有开发夹具，核验前后快照及封存索引的字节摘要均一致。负对照验证已注入的故障模式，包括分支漏失、替换界值及跨快照重放。完整 rich 查询覆盖和运行成本由本轮独立复核与成本报告给出。

复现命令使用与冻结依赖一致的 Python。

```powershell
python -B results/depth3_proof/check_negative_controls.py
python -B results/depth3_proof/check_symbolic_negative_controls.py
```

证据见 [`negative_controls.json`](results/depth3_proof/negative_controls.json) 和 [`symbolic_negative_controls.json`](results/depth3_proof/symbolic_negative_controls.json)。
