# RDINP G1-A 并发实验预检

完整 144 个配对已归档，见 [G1-A 判定报告](G1A_DECISION_REPORT.md)。当前等待人工确认。

当前阶段为 GOAL-1 的 G1-A。研究对象是公开固定回退点、有限边缘执行槽和双向不可靠通信下的纯计算任务。开发夹具为仓库生成器提供的图像，使用既有 Pillow 边缘检测流程。边缘档与本地档分别输出 512² 和 256²。该档位划分用于验证记账与执行路径，实际服务质量要求须由目标业务确认。

## 可执行路径

- run_concurrent.py 校准同机独立任务的平均持久授权至持久释槽时长，并按标称负载生成相同释放计划。在 4 或 8 个逻辑终端、1 或 2 个实际边缘执行槽上运行 B0、B1、B2-info。终端各有本地计算排队，边缘计算使用受监督进程，端边应用消息经 loopback TCP 传输。
- B1 复用既有应用 RPC 认证。任务 ID 绑定输入摘要。后续准入可以在 BUSY 后重试，已收到的许可含有限有效期及唯一执行代际。执行应答缺失时重查持久状态。终端在固定检查点决定是否回退，并通过幂等取消通道送达回退事实。执行点已获知公开回退点且不存在合格边缘结果时，可以按同一安全路径停止旧任务。B2-info 通过诊断通道让边缘获知实际回退，并执行相同安全停止与持久化规则。记录事实注入到提交取消之间的实际调度延迟。
- concurrent_store.py 区分执行资格、进程启动、结果提交、实际进程退出及槽位可复用。已开始的任务须由监督进程确认退出，才能释放该槽。APP_RELEASE 的时间采样在 SQLite 提交返回之后。重开账本时，失去原监督句柄的在途任务保守保留占用。结果提交跨过截止会保留尾段诊断。
- concurrent_audit.py 校验计划、逐任务表和事件日志，统计全部释放任务中的合格按期采用，以及低档回退、占槽尾段和可归因后继损失。区间用独立成对运行或故障簇重抽样。每个只运行一次的条件仅支持描述性统计。

默认模式使用预绑定任务，作用是校准和检查应用执行。启用 --c2-authorization 时，每个终端使用冻结 C2 的双边信任对与独立逻辑账本。应用授权必须接在同一任务的持久 C2 提交、回执核验和提交返回事件之后，实际执行槽继续由统一应用执行器管理。前向与反向消息按固定相对时间窗抑制。链路验证阶段再检查 TCP 重传。历史 5G-LENA 前传数据用于单独的容量敏感性验证。

## 复现

使用 Ubuntu 的独立实验目录以及 rdinp/requirements.txt 中的依赖。生成的运行目录必须是新目录。相同快照、夹具和参数应写入每份运行计划。

~~~bash
python -B rdinp/tools/generate_fixtures.py fixtures
python -B rdinp/experiments/durable-worker/test_concurrent_store.py -v
python -B rdinp/experiments/durable-worker/test_concurrent_audit.py -v
python -B rdinp/experiments/durable-worker/run_concurrent.py \
    --asset fixtures/camera.png --out runs/g1a-preflight \
    --terminals 4 --slots 1 --tasks 8
python -B rdinp/experiments/durable-worker/concurrent_audit.py \
    runs/g1a-preflight --out runs/g1a-preflight/audit.json
~~~

切换到真实授权时，在运行命令中加入 --c2-authorization 并使用新的输出目录。先读 [最新工程预检](G1A_ENGINEERING_PREFLIGHT_REPORT.md) 中的样本与故障范围。B2-ideal 的独立模型支持预绑定和 C2 授权计划。C2 模型将对应 B2-info 的最终权威提交时刻固定为外部条件，并回读原生权威记录校验。模型优先用已观测的完整停止链校准，缺少时使用同形态的六次独立诊断。

## G1-A 固定配对

[判定协议](G1A_DECISION_PROTOCOL.md) 固定真实工况和模型口径。两个形态分别使用新结果目录，各执行 72 个配对。需先校验执行快照，再执行完整网格，保留原生 C2、逐任务表、每对完成记录和校准。如下命令使用远端 Ubuntu 环境及冻结的依赖。

~~~bash
python -B rdinp/experiments/durable-worker/run_concurrent.py \
    --asset fixtures/camera.png --out runs/study-4x1 --terminals 4 --slots 1 \
    --tasks 12 --replicates 6 --c2-authorization --decision-study
python -B rdinp/experiments/durable-worker/run_concurrent.py \
    --asset fixtures/camera.png --out runs/study-8x2 --terminals 8 --slots 2 \
    --tasks 12 --replicates 6 --c2-authorization --decision-study
python -B rdinp/experiments/durable-worker/g1a_decision.py \
    runs/study-4x1 runs/study-8x2 --out runs/g1a-decision.json
~~~

原生 C2 各时间使用独立的启动基准，校验时通过 C2_CLOCK_BIND 对齐同一主机。该设计中已知回退点给出的动作边界见 [公开回退点的信息边界](PUBLIC_FALLBACK_INFORMATION_LEMMA.md)。

## 判定边界

B2-ideal 的即时释槽是假设条件，须与物理执行数据分开记录。G1-A 需要完整对照、独立配对重复，以及对差距能否由实际信息迟滞解释的复核。开发夹具的质量门槛、只运行一次的工况及安全停止的调度抖动均不能作为 Go 依据。如果公开截止与持久结果发布状态足够支持 B1 自行停止，单凭回退通知提前触发一次检查不能证明存在新的业务信息。任何进入 G1-B 的决定都以 G1-A 判定报告后的人工确认为准。
