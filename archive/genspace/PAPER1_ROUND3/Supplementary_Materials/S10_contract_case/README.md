# S10 封存 F2 合同案例

`frozen_base_instance.json` 与 `sealed_depth3_case.json` 是原封存文件的字节复制，包括合成的应用和网络偏好参数、公共资源快照、已交付候选与实际消息。`case_evidence.json` 给出原路径和 SHA-256、独立证明记录、协议检查点、实际角色、公开分数的 binary64 编码及双方保留效用。排名按封存的 `topk` 以 1 开始计数。`resource_cells.csv` 给出已选合同原解释器的逐格负载，`base` 表示角色附加成本以前的资源，`load` 来自实际模型预留动作，`slack` 为容量减去负载。EDGE 的保留角色在首时段增加 0.10，随后两时段在本地执行，不预留 EDGE。

该案例在已有有效深度 3 开发面板中运行，实际合同深度为 2，原 O1 已有协议。本轮只读取封存结果并在冻结模型上对已知见证及 27 个既有静态配置重算。归档协议消息来自历史执行。这些数据位于有限基准语义内，未使用持出实例。重算工具位于交付目录 `work/extract_contract_protocol.py`，在原项目中执行 `python -B PAPER1_ROUND3/work/extract_contract_protocol.py`。
