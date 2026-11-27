# REORCH-FAIL-01

独立的、确定性的 Python 仿真实验，用于检验协商期间资源耦合变化是否伴随固定分区损失。没有 LLM、ns-3 或 TFH 数据；运行期策略仅是诊断比较，不是新算法。只使用 Python 标准库。

## 运行

```powershell
python -m unittest discover -s tests -v
python run_experiment.py --instances 100 --seed-start 0 --workers 8
python analyze_results.py
```

默认扫描两个 family、三种 deadline tightness、三种 shift strength、四种 kappa，每组种子 0–99；72 组、7200 个配对实例、43200 次 episode。seed、参数和完整历史写入 `results/raw_results.csv`，分析汇总和图分别写入 `results/summary.csv` 和 `plots/`。每种策略由同一个生成函数和 seed 独立生成完全相同的实例，运行过程中没有额外随机事件。可通过 CLI 更改种子区间和实例数；正式结果对应默认配置。

## 实验定义

资源容量默认为 (100,100,100)，profile 的公开字段是需求向量与降级等级 0、1、2；用户效用仅供接受判断及事后统计，既不传给策略也不传给报价生成器。每个用户在已消耗时间 t 的阈值为 `start + min(1,t/deadline)*(reservation-start)`；阈值从随机初始值线性降至保留效用。超过 deadline 的报价不能接受。每组独立且并行报价，协调器先最大化可报价的 session 数，再最小化总公开降级等级，同分时按 deadline 紧迫度保留较优等级。无法同时容纳全组时允许报价可行子集。需求从当前档位向更高降级等级搜索，当前档位随所提出的 profile 或提交冲突更新。

所有 group 根据同一轮开始时的永久 ledger 报价。用户接受的每个 group 子集作为一个原子单位，按该子集中最早 deadline 排序，经全局 capacity 检查成功后一起提交；失败则都保持 active 并在下一轮继续。已提交合同永不改变，且每个策略均使用相同检查器。每轮耗时为 active groups 中 `1 + kappa*(size-1)` 的最大值；sequential 策略仅推进选中的单组，但其他 session 的 deadline 仍随时间流逝。rounds 是 session 级推进次数，messages 按每次推进两条计算；拒绝提交计数按受影响合同数计算。

## 耦合与实例

令 `a_r=demand_i,r/capacity_r`、`b_r=demand_j,r/capacity_r`。当前耦合分数为 `cos(a,b) * max_r(a_r+b_r) * max(0,min(deadline_i,deadline_j)-t)/(max(deadline_i,deadline_j)-t)`，分母不正时为零。即方向相似度、容量压力和当前有效期重叠比例的乘积。强变化实例中 A 的档位转向 EDGE 时 A–C 可自然增强；没有按轮数硬编码边。STATIC_CLUSTER 在初始图中连接分数至少为最强边 80% 的边，并取连通分量。

每个 seed 固定需求各维的 ±5% 扰动、deadline ±7% 扰动、用户效用偏移、保留效用及初始阈值。deadline 缩放系数 loose/medium/tight 分别为 1.3/1/0.72。COUPLING_SHIFT 的 weak/medium/strong 分别以 0.25/0.60/1.0 插值到给定 canonical profile；STATIC_COUPLING 则始终按初始向量同比例缩放，三个 strength 标签是重复的负对照，不能当作独立数据。扰动前的 canonical 数据列在 `config.py`。

## 策略与解释边界

B0 按 EDF 串行直到当前 session 完成或到期；B1 所有 active sessions 一组；B2 初始图固定聚类；B3 穷举初始 15 个集合分区并固定选择；B4 每场结束后依当前公开状态重选单个 session；O1 在每轮重新穷举当前 active sessions 的全部分区，切换开销为零。各策略共享完全相同的 engine、报价、接受、ledger 和 commit checker。

B3 和 O1 的“最优”指对当前公开状态的一步代理评分穷举最优：模拟各组的公开可行报价及按 deadline 顺序的资源占用，以报价数量、公开降级、紧迫性和耗时估分。该评分不访问私人效用，也不模拟未来随机事件；因此 B3 不保证 episode 结果上真正最优，O1 不是严格的理论上界，甚至不保证优于每个静态策略。O1 每轮重算包括事件未改变的情况，但如果状态不变分区可不变。不能仅凭该诊断结果证明所有运行期重分区的潜在收益上界。

`GATE_REPORT.md` 给出预先编码的判定规则和结果。未取得稳定优势时，应解读为该模拟和代理策略下证据不足，而非对所有可能策略或真实系统的否证。测试覆盖资源账本、配对用户参数、无变化零开销对照、对称情形及 Bell(4)=15；对称时在完全平局下具体获胜标签可由确定性字典序决定，测试的是组合层面的置换不变性。
