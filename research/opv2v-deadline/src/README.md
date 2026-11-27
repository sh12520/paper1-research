# 代码和最小复现

以下三个文件按原研究目录 `scripts/` 的同名文件逐字节复制。输入、工具链和检查范围分别列出。

| 文件 | 用途和依赖 | 原件 SHA-256 |
| --- | --- | --- |
| [opv2v_network.py](opv2v_network.py) | R1 相对网络时钟与融合阶段模型，标准库 | `b7a34a7ea5bb419304c3fbce438803067631e1e51e1a03af92583ec1cecb8ed3` |
| [opv2v_r23_prefilter.py](opv2v_r23_prefilter.py) | R2.3 按原阈值预筛、解码、范围过滤、旋转 NMS；依赖下游模型、Torch、NumPy、OpenCOOD。原 CLI 额外定位封存 R2.2 GPU 检测头状态 | `9d1c7ce5e91c07361959f1acf97033d48a842beea0672d44f8d00614256b2776` |
| [opv2v_r25_pipeline.py](opv2v_r25_pipeline.py) | R2.5/2.6 包解析、缓存、完整融合、检测头和主机后处理。需要原有 FrameReplay、原生模型以及同一接收语义 | `2ef41f6c5250107c2cdae93fb0c423a0f7b131cb0877fe6f266b294989687950` |

## 默认验证

从私有仓库根目录执行。

```bash
python3 -B research/opv2v-deadline/src/check_packet_clock.py
```

[夹具](r1_packet_clock_frame0000.json)按原面板序号取首帧 `2021_08_18_19_48_05/000070/1045`。固定 256 KiB、100 Mbps、RTT 10 ms，保留 `blindmap`、`feedback`、`parallel`、`followup` 的原应用字节、控制字节和整个时钟账本。夹具记录原始逐帧文件与原网络模块 SHA-256；只摘录时序字段，报告它们的精确重算。此检查只运行网络模型。

交接时在 Ubuntu 使用 Python 3.10.12 检查通过，`/usr/bin/time` 墙钟 0.04 s，峰值 RSS 17,408 KiB，退出码 0。四组应用层总字节分别为 262,026、262,040、261,452、261,452 B。四种时序模式沿用原 R1 命名。后续 A/B/C/D 的边际对照定义见 [EVIDENCE.md](../EVIDENCE.md)。

## 原实验入口及版本

- R1 模型推理从原 `scripts/run_opv2v_formal.py` 进入；普通无反馈补包从 `scripts/run_opv2v_feedback_control.py`，发送方优化从 `scripts/run_opv2v_sender_optimized.py`。这些运行器和全量 JSONL 留在原工程。
- R2.6 实际 GPU 推理与等价核对是原 `scripts/run_opv2v_r26.py`。它按单帧执行并从原 R2.5 继承 A/B 实测计时。CPU 主报告与敏感性从 `scripts/report_opv2v_r26.py` 及 `scripts/report_opv2v_r26_resources.py` 进入。队列诊断对照尚未执行。
- 冻结 R2.6 runner 与原后续快照 `35da85d5b11c90e508f555d6f8348910a86982be` 对应。原研究工程运行时根 HEAD 未记录，快照创建在运行后。历史 GPU 计时用 RTX A6000、驱动 580.178.04、Torch 2.15.0+cu132 及两个 Torch CPU 线程。模型与归档身份见 [EVIDENCE.md](../EVIDENCE.md)。
- 完整模型复现需要原冻结面板和预处理、上游固定 commit、匹配权重、应用包字节、原 CUDA 路径和可用 GPU。以 [REFERENCES.md](../REFERENCES.md) 的发布源获取，不自动下载、派发或运行冻结确认。
