"""Summarize paired Step1 simulation runs, with Chinese tables and figures."""

import argparse
import csv
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import quantiles


METHODS = {
    "Fixed-Intent": "固定意图",
    "Reactive-ReNeg": "反应式重协商",
    "Static-Fallback": "静态回退",
    "Structured-RDINP": "结构化 RDINP",
}
TARGET = "Structured-RDINP"
CENTERS = {"load": 0.7, "loss": 0.05, "dip": 0.5, "deadline_ms": 600.0}
AXES = {
    "load": ("负载率", "Offered load"),
    "loss": ("坏状态窗占比", "Bad-window occupancy (%)"),
    "dip": ("空口速率跌幅", "Access-rate drop (%)"),
    "deadline_ms": ("截止期（ms）", "Deadline (ms)"),
}
COUNTS = ("released", "high", "light", "local", "missed")
TOTALS = ("utility_sum", "control_bytes", "rounds_sum", "negotiation_ms_sum")
METRICS = {
    "high_rate": ("high", "高质量边缘率", "High-grade edge"),
    "light_rate": ("light", "轻量边缘率", "Light-grade edge"),
    "local_rate": ("local", "本地交付率", "Local"),
    "on_time_rate": ("on_time", "按期交付率", "On-time delivery"),
    "miss_rate": ("missed", "未按期交付率", "Deadline miss"),
    "utility_per_task": ("utility_sum", "平均效用", "Utility per task"),
    "control_bytes_per_task": ("control_bytes", "控制字节/任务", "Control bytes per task"),
    "rounds_per_task": ("rounds_sum", "轮次/任务", "Rounds per task"),
    "negotiation_ms_per_task": ("negotiation_ms_sum", "协商时间（ms）/任务", "Negotiation ms per task"),
}
BOOTSTRAPS = 2000


def load_pairs(path):
    pairs = defaultdict(dict)
    coordinates = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = {"scenario", "seed", "method", *CENTERS, *COUNTS, *TOTALS}
        missing = expected - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, start=2):
            try:
                scenario, method = row["scenario"], row["method"]
                seed = int(row["seed"])
                factors = tuple(float(row[field]) for field in CENTERS)
                counts = {field: int(row[field]) for field in COUNTS}
                totals = {field: float(row[field]) for field in TOTALS}
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid cell on line {line}: {exc}") from exc
            if not scenario or method not in METHODS or method in pairs[scenario, seed]:
                raise ValueError(f"Invalid or duplicate scenario/seed/method on line {line}")
            if not all(math.isfinite(value) for value in (*factors, *totals.values())):
                raise ValueError(f"Nonfinite input on line {line}")
            if coordinates.setdefault(scenario, factors) != factors:
                raise ValueError(f"Inconsistent factor settings for scenario {scenario}")
            if min(counts.values()) < 0 or counts["released"] != sum(counts[k] for k in COUNTS[1:]):
                raise ValueError(f"Grade counts do not sum to released on line {line}")
            pairs[scenario, seed][method] = {**counts, **totals, "on_time": counts["released"] - counts["missed"]}
    if not pairs:
        raise ValueError("per_run.csv has no data rows")
    for key, block in pairs.items():
        if set(block) != set(METHODS) or len({row["released"] for row in block.values()}) != 1:
            raise ValueError(f"Incomplete method pairing or unequal releases for scenario/seed {key}")
    return pairs, {scenario: dict(zip(CENTERS, values)) for scenario, values in coordinates.items()}


def aggregate(pairs):
    for method in METHODS:
        rows = [block[method] for block in pairs.values()]
        totals = {name: sum(row[name] for row in rows) for name in (*COUNTS, *TOTALS, "on_time")}
        n = totals["released"]
        rates = {key: totals[field] / n if n else None for key, (field, _, _) in METRICS.items()}
        yield {"method": method, "runs": len(rows), **totals, **rates}


def paired_differences(pairs, axis, level):
    blocks = defaultdict(list)
    for (_, seed), block in pairs.items():
        blocks[seed].append(block)
    ordered = [blocks[seed] for seed in sorted(blocks)]
    rng = random.Random(20261128)
    samples = [rng.choices(range(len(ordered)), k=len(ordered)) for _ in range(BOOTSTRAPS)] if len(ordered) >= 2 else []
    released = [sum(pair[TARGET]["released"] for pair in rows) for rows in ordered]
    for baseline in METHODS:
        if baseline == TARGET:
            continue
        for metric, (field, _, _) in METRICS.items():
            deltas = [sum(pair[TARGET][field] - pair[baseline][field] for pair in rows) for rows in ordered]
            estimates = []
            for draw in samples:
                denominator = sum(released[index] for index in draw)
                if denominator:
                    estimates.append(sum(deltas[index] for index in draw) / denominator)
            ci = quantiles(estimates, n=40, method="inclusive") if len(estimates) >= 2 else []
            yield {
                "axis": axis, "level": level, "method": TARGET, "baseline": baseline,
                "metric": metric, "paired_runs": len(pairs), "seed_blocks": len(ordered),
                "paired_released": sum(released), "delta": sum(deltas) / sum(released) if sum(released) else None,
                "ci95_low": ci[0] if ci else None, "ci95_high": ci[-1] if ci else None,
                "bootstrap_reps": len(estimates),
            }


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def make_plots(out, overall, slices):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import fontManager

    fonts = {font.name for font in fontManager.ttflist}
    font = next((name for name in ("Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "WenQuanYi Zen Hei") if name in fonts), None)
    if font:
        plt.rcParams.update({"font.family": font, "axes.unicode_minus": False})
    palette = ("#355970", "#BB6543", "#8C729C", "#188273")

    def label(metric):
        return METRICS[metric][1 if font else 2]

    def values(rows, metric, scale=1):
        return [row[metric] * scale if row[metric] is not None else math.nan for row in rows]

    names = [METHODS[row["method"]] if font else row["method"] for row in overall]
    grades = ("high_rate", "light_rate", "local_rate", "miss_rate")
    fig, ax = plt.subplots(figsize=(9, 4.6), layout="constrained")
    bottom = [0.0] * len(overall)
    for metric, color in zip(grades, ("#176B5D", "#5E91AC", "#D6A24F", "#C66558")):
        part = values(overall, metric, 100)
        ax.bar(names, part, bottom=bottom, label=label(metric), color=color, width=0.58)
        bottom = [a + b for a, b in zip(bottom, part)]
    ax.set_ylim(0, 100)
    ax.set_ylabel("占释放任务比例（%）" if font else "Share of released tasks (%)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=4, frameon=False)
    fig.savefig(out / "overall_grades.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.8), layout="constrained")
    for ax, metric in zip(axes, ("control_bytes_per_task", "rounds_per_task", "negotiation_ms_per_task")):
        ax.bar(names, values(overall, metric), color=palette, width=0.58)
        ax.set_ylabel(label(metric))
        ax.tick_params(axis="x", rotation=28, labelsize=8)
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)
    fig.savefig(out / "overall_control.png", dpi=170)
    plt.close(fig)

    chart_axes = []
    for axis, axis_titles in AXES.items():
        rows = [row for row in slices if row["axis"] == axis]
        if not rows:
            continue
        fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), layout="constrained")
        scale_x = 100 if axis in {"loss", "dip"} else 1
        axis_label = axis_titles[0 if font else 1] + ("（%）" if font and scale_x == 100 else "")
        for ax, metric in zip(axes, ("on_time_rate", "utility_per_task", "control_bytes_per_task")):
            for (method, cn), color, marker in zip(METHODS.items(), palette, ("o", "D", "s", "^")):
                selected = [row for row in rows if row["method"] == method]
                scale_y = 100 if metric == "on_time_rate" else 1
                ax.plot([row["level"] * scale_x for row in selected], values(selected, metric, scale_y),
                        color=color, marker=marker, label=cn if font else method)
            ax.set(xlabel=axis_label, ylabel=label(metric) + (" (%)" if metric == "on_time_rate" else ""))
            ax.grid(alpha=0.25)
        axes[0].legend(fontsize=8, frameon=False)
        fig.savefig(out / f"slice_{axis}.png", dpi=170)
        plt.close(fig)
        chart_axes.append(axis)
    return font, chart_axes


def format_value(value, scale=1, precision=2):
    return "—" if value is None else f"{value * scale:.{precision}f}"


def write_report(out, pairs, overall, paired, font, chart_axes):
    lines = [
        "# Step1 探索性分析",
        "",
        f"覆盖 {len({scenario for scenario, _ in pairs})} 个场景，"
        f"{len({seed for _, seed in pairs})} 个种子和 {len(pairs)} 组完整的方法对照。",
        "总览直接汇总全部释放任务。未按期交付的任务同样进入分母，各质量档率互斥。",
        "",
        "| 方法 | 释放 | 高质量边缘 | 轻量边缘 | 本地 | 未按期 | 按期率 | 平均效用 | 控制字节/任务 | 轮次/任务 | 协商 ms/任务 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in overall:
        counts = " | ".join(str(row[k]) for k in COUNTS)
        rate = format_value(row["on_time_rate"], scale=100) + "%" if row["on_time_rate"] is not None else "—"
        costs = " | ".join(format_value(row[k], precision=4 if k == "utility_per_task" else 2) for k in
                           ("utility_per_task", "control_bytes_per_task", "rounds_per_task", "negotiation_ms_per_task"))
        lines.append(f"| {row['method']} | {counts} | {rate} | {costs} |")
    lines.extend([
        "",
        "## 配对差值",
        "",
        f"对同一场景、同一随机种子的运行配对。按种子整块抽取 {BOOTSTRAPS} 次，同种子的各场景一起进入重采样。",
        "差值与区间仍按释放任务数归一化。百分位区间用于探索，种子少时尤其不能视为确认性统计检验。",
        "",
        "| 对照 | 指标 | 结构化 RDINP 减去对照 | 探索性 95% 区间 |",
        "|---|---|---:|---:|",
    ])
    for row in paired:
        if row["axis"] != "overall" or row["metric"] not in {
            "on_time_rate", "utility_per_task", "control_bytes_per_task",
        }:
            continue
        pp = row["metric"] == "on_time_rate"
        scale, unit = (100, " 个百分点") if pp else (1, "")
        precision = 4 if row["metric"] == "utility_per_task" else 2
        delta = format_value(row["delta"], scale, precision)
        interval = "—" if row["ci95_low"] is None else (
            f"[{format_value(row['ci95_low'], scale, precision)}, {format_value(row['ci95_high'], scale, precision)}]{unit}"
        )
        lines.append(f"| {row['baseline']} | {METRICS[row['metric']][1]} | {delta}{unit if row['delta'] is not None else ''} | {interval} |")
    lines.extend([
        "",
        "## 单因素切片",
        "",
        "每张图只变动横轴因素。其余因素固定在负载率 0.7、坏状态窗占比 0.05、降容幅度 0.5 和截止期 600 ms 的参考值。",
        "坏状态窗占比是输入模型参数，与实测丢包率的含义不同。",
        "",
        "- [总览质量档](overall_grades.png) 与 [总览控制开销](overall_control.png)",
    ])
    for axis, (title, _) in AXES.items():
        lines.append(f"- [{title}切片](slice_{axis}.png)" if axis in chart_axes else f"- {title}切片缺少与参考设置匹配的运行")
    if not font:
        lines.extend(["", "本机 Matplotlib 未检测到支持的中文字体，图表使用英文坐标标签。"])
    lines.extend([
        "",
        "[总览表](overall.csv) · [全场景汇总](per_scenario.csv) · [切片表](slices.csv) · [完整配对差值和区间](paired_differences.csv)",
    ])
    (out / "ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(directory):
    pairs, coordinates = load_pairs(directory / "per_run.csv")
    out = directory / "analysis"
    out.mkdir(exist_ok=True)
    scenarios = defaultdict(dict)
    for key, block in pairs.items():
        scenarios[key[0]][key] = block
    overall = list(aggregate(pairs))
    per_scenario = [
        {"scenario": name, **coordinates[name], **row}
        for name, group in sorted(scenarios.items()) for row in aggregate(group)
    ]
    slices = []
    paired = list(paired_differences(pairs, "overall", "all"))
    for axis in AXES:
        levels = defaultdict(dict)
        for name, group in scenarios.items():
            coord = coordinates[name]
            if all(math.isclose(coord[field], center, rel_tol=0, abs_tol=1e-9)
                   for field, center in CENTERS.items() if field != axis):
                levels[coord[axis]].update(group)
        for level, group in sorted(levels.items()):
            slices.extend({"axis": axis, "level": level, **row} for row in aggregate(group))
            paired.extend(paired_differences(group, axis, level))
    headers = list(overall[0])
    write_csv(out / "overall.csv", headers, overall)
    write_csv(out / "per_scenario.csv", ["scenario", *CENTERS, *headers], per_scenario)
    write_csv(out / "slices.csv", ["axis", "level", *headers], slices)
    write_csv(out / "paired_differences.csv", list(paired[0]), paired)
    font, chart_axes = make_plots(out, overall, slices)
    write_report(out, pairs, overall, paired, font, chart_axes)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    print(analyze(args.result_dir).resolve())
