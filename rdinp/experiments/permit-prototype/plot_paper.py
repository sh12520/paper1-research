"""Render paper figures directly from the frozen simulation and live prototype data."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator, PercentFormatter

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / "structured-fast-slow" / "evidence"
METHODS = ("Fixed-Intent", "Reactive-ReNeg", "Static-Fallback", "Structured-RDINP")
METHOD_NAMES = ("固定意图", "反应式重协商", "静态回退", "结构化 RDINP")
METHOD_COLORS = ("#43536B", "#B85132", "#956400", "#006F72")
PROTOTYPE = (METHODS[1], METHODS[3])
PROTOTYPE_NAMES = (METHOD_NAMES[1], METHOD_NAMES[3])
PROTOTYPE_COLORS = (METHOD_COLORS[1], METHOD_COLORS[3])
METHOD_STYLES = (
    ("o", "-"),
    ("s", "--"),
    ("D", "-."),
    ("^", "-"),
)
GRADES = ("main", "light", "local", "missed")
GRADE_NAMES = ("边缘主档", "边缘轻量档", "本地兜底", "超期或失败")
GRADE_COLORS = ("#124E61", "#008279", "#E8B34D", "#ACB3BD")
CONDITIONS = {"plain": "基准链路", "half": "持续降半", "dynamic": "时变链路"}
CONDITION_COLORS = {"plain": "#43536B", "half": "#A45E2F", "dynamic": "#006F72"}
AXES = {
    "load": ("资源负载率", 1),
    "loss": ("坏状态窗占比（%）", 100),
    "dip": ("空口速率跌幅（%）", 100),
    "deadline_ms": ("截止期（ms）", 1),
}


def configure():
    available = {font.name for font in font_manager.fontManager.ttflist}
    families = ("Microsoft YaHei", "Noto Sans SC", "Noto Sans CJK SC", "SimHei")
    font = next((name for name in families if name in available), None)
    if font is None:
        raise RuntimeError("Install a Chinese font: Microsoft YaHei, Noto Sans SC or Noto Sans CJK SC.")
    plt.rcParams.update({
        "font.family": font,
        "font.size": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.65,
        "axes.labelcolor": "#263445",
        "axes.edgecolor": "#526170",
        "text.color": "#263445",
        "xtick.color": "#263445",
        "ytick.color": "#263445",
        "xtick.major.width": 0.65,
        "ytick.major.width": 0.65,
        "axes.titleweight": "bold",
        "legend.frameon": False,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })
    return font


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(fig, out, name):
    fig.savefig(out / f"{name}.png", dpi=600)
    fig.savefig(out / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def figure_legend(fig, handles, labels, *, columns):
    fig.legend(handles, labels, loc="outside upper center", ncols=columns, columnspacing=1.05,
               handlelength=1.7)


def y_grid(ax):
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#D7DFE6", linewidth=.55)


def series_bars(ax, values, labels, colors, label, *, display=".2f"):
    indices = range(len(values))
    boxes = ax.bar(indices, values, width=.53, color=colors)
    ax.set_xticks(indices, labels)
    ax.bar_label(boxes, labels=[format(x, display) for x in values], padding=2, fontsize=8)
    ax.set_ylabel(label)
    ax.set_ylim(0, max(values) * 1.21 if any(values) else 1)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    y_grid(ax)


def grades(ax, values, labels):
    base = [0.0] * len(labels)
    indices = range(len(labels))
    for fractions, color, name in zip(zip(*values), GRADE_COLORS, GRADE_NAMES):
        bars = ax.bar(indices, fractions, bottom=base, color=color, width=.58, label=name)
        for box, ratio, low in zip(bars, fractions, base):
            if ratio > .105:
                color_text = "white" if name in GRADE_NAMES[:2] else "#263445"
                ax.text(box.get_x() + box.get_width() / 2, low + ratio / 2,
                        f"{ratio:.1%}", ha="center", va="center", color=color_text, fontsize=8)
        base = [x + y for x, y in zip(base, fractions)]
    ax.set_xticks(indices, labels)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("占全部释放任务比例")
    y_grid(ax)


def simulation_overview(out, path):
    rows = {r["method"]: r for r in read_csv(path / "overall.csv")}
    assert set(rows) == set(METHODS)
    rows = [rows[m] for m in METHODS]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.15), layout="constrained")
    short = ("固定", "重协商", "静态回退", "RDINP")
    rate_rows = [
        [int(row[col]) / int(row["released"]) for col in ("high", "light", "local", "missed")]
        for row in rows
    ]
    grades(axes[0, 0], rate_rows, short)
    axes[0, 0].set_title("（a）最终交付档位", loc="left")
    for ax, (metric, title, unit, display) in zip(axes.flat[1:], (
        ("control_bytes_per_task", "控制消息体", "字节/任务", ",.0f"),
        ("rounds_per_task", "协商轮次", "轮/任务", ".2f"),
        ("negotiation_ms_per_task", "协商耗时", "毫秒/任务", ".1f"),
    )):
        series_bars(ax, [float(r[metric]) for r in rows], short, METHOD_COLORS, unit, display=display)
        panel = ("b", "c", "d")[list(axes.flat[1:]).index(ax)]
        ax.set_title(f"（{panel}）{title}", loc="left")
    handles, names = axes[0, 0].get_legend_handles_labels()
    figure_legend(fig, handles, names, columns=4)
    save(fig, out, "01_sim_overview")


def simulation_sensitivity(out, path):
    rows = read_csv(path / "slices.csv")
    fig, axes = plt.subplots(4, 3, figsize=(7.2, 8.1), layout="constrained")
    metrics = ("on_time_rate", "utility_per_task", "control_bytes_per_task")
    for column, title in enumerate(("按期采用率", "平均效用", "控制消息体（字节/任务）")):
        axes[0, column].set_title(title)
    for row_index, (axis, (label, scale)) in enumerate(AXES.items()):
        for ax, metric in zip(axes[row_index], metrics):
            for method, name, color, (marker, line) in zip(METHODS, METHOD_NAMES, METHOD_COLORS, METHOD_STYLES):
                subset = sorted(
                    (r for r in rows if (r["axis"], r["method"]) == (axis, method)),
                    key=lambda r: float(r["level"]),
                )
                points = [float(r["level"]) * scale for r in subset]
                ax.plot(points, [float(r[metric]) for r in subset], color=color, linestyle=line,
                        label=name, marker=marker, markersize=4.0, linewidth=1.15)
                ax.set_xticks(points, [f"{x:g}" for x in points])
            ax.set_xlabel(label, fontsize=8)
            ax.tick_params(axis="both", labelsize=7.5)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
            if metric == "on_time_rate":
                ax.set_ylim(0.2, 1.055)
                ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
            elif metric == "utility_per_task":
                ax.set_ylim(0.2, 1.0)
            else:
                ax.set_ylim(0, 3000)
                ax.set_yticks([0, 1000, 2000, 3000], ["0", "1千", "2千", "3千"])
            y_grid(ax)
    handles, names = axes[0, 0].get_legend_handles_labels()
    figure_legend(fig, handles, names, columns=4)
    save(fig, out, "02_sim_sensitivity")


def simulation_fast_switch(out, path):
    source = [r for r in read_csv(path) if r["contrast"] == "fast_given_menu_admission"]
    cohorts = ("all", "400ms", "600ms", "800ms")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
    for ax, (metric, title, scale, fmt) in zip(axes, (
        ("effective_utility", "平均效用差", 1.0, "+.3f"),
        ("edge_adopted", "边缘采用率差（百分点）", 100, "+.1f"),
    )):
        rows = {r["cohort"]: r for r in source if r["metric"] == metric}
        values = [float(rows[c]["difference"]) * scale for c in cohorts]
        low = [float(rows[c]["ci95_low"]) * scale for c in cohorts]
        high = [float(rows[c]["ci95_high"]) * scale for c in cohorts]
        ax.errorbar(values, range(4), xerr=([v - l for v, l in zip(values, low)],
                                          [h - v for v, h in zip(values, high)]),
                    fmt="o", capsize=3, color="#006F72", linewidth=1.3, markersize=4)
        ax.set_yticks(range(4), ["总体", "400 ms", "600 ms", "800 ms"])
        ax.invert_yaxis()
        ax.axvline(0, color="#526170", linestyle="--", linewidth=.65)
        ax.set_xlim(0 if min(low) >= 0 else min(low) * 1.05, max(high) * 1.30)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.set_xlabel(title)
        for index, (v, h) in enumerate(zip(values, high)):
            ax.annotate(format(v, fmt), (h, index), xytext=(5, 0), textcoords="offset points",
                        fontsize=8, va="center")
    save(fig, out, "03_sim_fast_switch")


def paired_tasks(pairs):
    rows = read_csv(pairs / "per_task.csv")
    lookup = {}
    for row in rows:
        k = (row["condition"], row["seed"], row["task_id"])
        match = lookup.setdefault(k, {})
        assert row["method"] not in match
        match[row["method"]] = row
    assert all(set(row) == set(PROTOTYPE) for row in lookup.values())
    return rows, lookup


def prototype_delivery(out, pairs):
    rows, paired = paired_tasks(pairs)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.35), layout="constrained")
    frac = []
    for method in PROTOTYPE:
        grades_seen = Counter(r["grade"] for r in rows if r["method"] == method)
        frac.append([grades_seen[k] / sum(grades_seen.values()) for k in GRADES])
    grades(axes[0], frac, PROTOTYPE_NAMES)
    axes[0].set_title("（a）最终交付档位", loc="left")

    blocks = defaultdict(list)
    for (condition, seed, _), arm in paired.items():
        blocks[(condition, seed)].append(
            float(arm[PROTOTYPE[1]]["utility"]) - float(arm[PROTOTYPE[0]]["utility"])
        )
    ax = axes[1]
    labels = list(CONDITIONS.values()) + ["总体"]
    for i, case in enumerate(CONDITIONS):
        vals = [mean(effects) for (condition, _), effects in blocks.items() if condition == case]
        offsets = [(j - (len(vals) - 1) / 2) * .11 for j in range(len(vals))]
        ax.scatter([i + x for x in offsets], vals, facecolors="white", edgecolors=CONDITION_COLORS[case],
                   linewidth=.9, s=25, zorder=3)
        ax.scatter(i, mean(vals), marker="D", color=CONDITION_COLORS[case], s=22, zorder=4)
    total = math.fsum(d for effects in blocks.values() for d in effects) / len(paired)
    ax.scatter(3, total, marker="D", color="#263445", s=32, zorder=4)
    ax.axhline(0, color="#526170", linewidth=.7, linestyle="--")
    ax.set_xticks(range(4), labels)
    ax.set_ylabel("配对任务平均效用差")
    ax.set_title("（b）结构化 RDINP 相对重协商", loc="left")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.annotate(f"{total:+.4f}", (3, total), xytext=(0, 7), textcoords="offset points",
                ha="center", fontsize=8)
    y_grid(ax)
    handles, names = axes[0].get_legend_handles_labels()
    figure_legend(fig, handles, names, columns=4)
    save(fig, out, "04_prototype_delivery")


def prototype_control(out, pairs, c2):
    arms = read_csv(pairs / "per_arm.csv")
    tasks = read_csv(pairs / "per_task.csv")
    count = Counter(row["method"] for row in tasks)
    issued = []
    ctrl = []
    extra = []
    for method in PROTOTYPE:
        rows = [row for row in arms if row["method"] == method]
        issued.append(sum(int(row["permit_total_control_bytes"]) for row in rows) / count[method])
        ctrl.append(sum(int(row["control_body_bytes"]) for row in rows) / count[method])
        extra.append(sum(int(row["extra_select_requests"]) for row in rows) / count[method])
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.95), layout="constrained")
    short = ("重协商", "RDINP")
    ax = axes[0]
    regions = ax.bar(range(2), issued, width=.54, color="#8EB6C0", label="许可签发与续签")
    totals = ax.bar(range(2), [t - i for t, i in zip(ctrl, issued)], width=.54, bottom=issued,
                    color="#194E61", label="其他控制")
    ax.bar_label(totals, labels=[f"{x:,.0f}" for x in ctrl], padding=2, fontsize=8)
    ax.set_xticks(range(2), short)
    ax.set_ylim(0, max(ctrl) * 1.22)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.set_ylabel("字节/任务")
    ax.set_title("（a）整会话控制开销", loc="left")
    y_grid(ax)
    series_bars(axes[1], extra, short, PROTOTYPE_COLORS, "额外切档请求/任务", display=".3f")
    axes[1].set_title("（b）上传后选择请求", loc="left")
    signed = float(c2["actual_body_bytes_per_released_task"])
    series_bars(axes[2], [signed, issued[1]], ["逐任务\nC2", "会话许可\nRDINP"],
                ("#526170", PROTOTYPE_COLORS[1]), "签发字节/任务", display=",.0f")
    axes[2].set_title("（c）签发路径开销", loc="left")
    figure_legend(fig, (regions, totals), ("许可签发与续签", "其他控制"), columns=2)
    save(fig, out, "05_prototype_control")


def prototype_headroom(out, pairs, c2):
    paths = {row["upload"]: row for row in read_json(pairs / "headroom.json")}
    plan = read_json(pairs / "plan.json")
    deadline = plan["deadline_ms"]
    cutoff = deadline - plan["fallback_reserve_ms"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3), layout="constrained")
    ax = axes[0]
    names = ("上传前选轻量", "主档上传后切换")
    has_censored = False
    for i, k in enumerate(("light", "main")):
        row = paths[k]
        accepted = [r["grade"] == "light" for r in row["rows"]]
        times = [float(r["end_to_end_ms"]) if ok else deadline for r, ok in zip(row["rows"], accepted)]
        xs = [i + .08 * ((j % 5) - 2) for j in range(len(times))]
        ax.scatter([x for x, ok in zip(xs, accepted) if ok],
                   [t for t, ok in zip(times, accepted) if ok],
                   marker="o", facecolors="white", edgecolors=PROTOTYPE_COLORS[i],
                   s=24, linewidth=.9, zorder=3)
        if not all(accepted):
            ax.scatter([x for x, ok in zip(xs, accepted) if not ok],
                       [t for t, ok in zip(times, accepted) if not ok],
                       marker="x", color=PROTOTYPE_COLORS[i], s=24, zorder=3,
                       label=None if has_censored else f"未采用轻量结果（按 {deadline} ms 计）")
            has_censored = True
        p95 = cutoff - float(row["margin_p95_ms"])
        ax.scatter(i, p95, marker="D", color=PROTOTYPE_COLORS[i], s=32, zorder=4)
        ax.annotate(f"p95 {p95:.1f}", (i, p95), xytext=(0, -16 if i else 6),
                    textcoords="offset points", fontsize=8, ha="center", va="bottom",
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": .4})
    ax.axhline(cutoff, color="#526170", linewidth=.7, linestyle="--", label=f"边缘采用截止 {cutoff} ms")
    ax.set_xlim(-.45, 1.45)
    ax.set_xticks(range(2), names)
    ax.set_ylabel("端到端实测时长（ms）")
    ax.set_title("（a）持续降半时的两条轻量路径", loc="left")
    ax.legend(loc="lower right", fontsize=8)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    y_grid(ax)

    ax = axes[1]
    trial = [float(row["release_to_terminal_ns"]) / 1e6 for row in c2["trials"]]
    ax.scatter(range(1, len(trial) + 1), trial, color="#526170", s=18)
    ax.axhline(400, color="#A23B39", linewidth=.8, linestyle="--", label="400 ms 参考线")
    ax.set_xlabel("逐任务签发序号")
    ax.set_ylabel("仅控制耗时（ms）")
    ax.set_title("（b）独立 C2 四阶段签发", loc="left")
    ax.legend(loc="upper right", fontsize=8)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    y_grid(ax)
    save(fig, out, "06_prototype_headroom")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step1", type=Path, default=FROZEN / "step1-20261128-r02" / "analysis")
    parser.add_argument("--attribution", type=Path,
                        default=FROZEN / "step1-attribution-20261128-r02" / "contrasts.csv")
    parser.add_argument("--pairs", type=Path, default=HERE / "runs" / "step2-paired-20261128-r01")
    parser.add_argument("--c2", type=Path, default=HERE / "runs" / "c2-baseline-02" / "c2_cost.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    font = configure()
    args.out.mkdir(parents=True, exist_ok=True)
    simulation_overview(args.out, args.step1)
    simulation_sensitivity(args.out, args.step1)
    simulation_fast_switch(args.out, args.attribution)
    c2 = read_json(args.c2)
    prototype_delivery(args.out, args.pairs)
    prototype_control(args.out, args.pairs, c2)
    prototype_headroom(args.out, args.pairs, c2)
    print(f"Six 600-DPI PNG and vector PDF figure pairs written using {font}.")


if __name__ == "__main__":
    main()
