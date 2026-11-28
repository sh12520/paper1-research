"""Render publication figures from audited 16-seed RDINP prototype results."""

from __future__ import annotations

import argparse
from pathlib import Path

from plot_paper import (
    CONDITIONS,
    GRADES,
    MaxNLocator,
    configure,
    figure_legend,
    grades,
    plt,
    read_json,
    save,
    y_grid,
)


METHODS = ("Structured-RDINP", "Reactive-ReNeg", "Same-Permit-No-Switch")
METHOD_LABELS = ("结构化 RDINP", "反应式重协商", "同许可禁快切")
METHOD_SHORT = ("RDINP", "重协商", "禁快切")
METHOD_COLORS = ("#006F72", "#B85132", "#43536B")
CASES = ("overall", "plain", "half", "dynamic")
CASE_LABELS = ("总体", *(CONDITIONS[case] for case in CASES[1:]))
CONTRASTS = (
    ("structured_minus_reactive", "结构化 RDINP − 反应式重协商", "#B85132", "o"),
    ("structured_minus_no_switch", "结构化 RDINP − 同许可禁快切", "#43536B", "s"),
)


def arm_groups(summary):
    return {"overall": summary["methods"], **summary["by_condition"]}


def grade_fraction(arm):
    counts = [arm[grade] for grade in GRADES]
    total = arm["released"]
    if total <= 0 or sum(counts) != total:
        raise ValueError("Delivery grades do not account for all released tasks")
    return [count / total for count in counts]


def delivery_figure(groups, out):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.3), layout="constrained")
    for panel, (ax, case, label) in enumerate(zip(axes.flat, CASES, CASE_LABELS)):
        arms = groups[case]
        grades(ax, [grade_fraction(arms[method]) for method in METHODS], METHOD_SHORT)
        miss = " / ".join(str(arms[method]["missed"]) for method in METHODS)
        ax.set_xlabel(f"未按期任务数（依列顺序）  {miss}", fontsize=8)
        ax.set_title(f"（{'abcd'[panel]}）{label}", loc="left")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure_legend(fig, handles, labels, columns=4)
    save(fig, out, "07_expansion_delivery")


def paired_effect_figure(contrasts, out):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 3.25), layout="constrained")
    metrics = (
        ("utility", "（a）质量效用差", 1),
        ("edge_adoption_rate", "（b）边缘采用率差（百分点）", 100),
        ("timely_adoption_rate", "（c）总按期率差（百分点）", 100),
    )
    for panel, (ax, (key, xlabel, scale)) in enumerate(zip(axes, metrics)):
        for (contrast, label, color, marker), offset in zip(CONTRASTS, (-0.14, 0.14)):
            rows = [contrasts[contrast][case][key] for case in CASES]
            points = [row["delta"] * scale for row in rows]
            lo = [row["ci95"][0] * scale for row in rows]
            hi = [row["ci95"][1] * scale for row in rows]
            ticks = [i + offset for i in range(len(CASES))]
            # Draw interval endpoints separately. A percentile interval does not
            # require the original point estimate to lie inside its endpoints.
            ax.hlines(ticks, lo, hi, color=color, linewidth=1.05)
            ax.vlines([*lo, *hi], [y - 0.055 for y in ticks] * 2,
                      [y + 0.055 for y in ticks] * 2, color=color, linewidth=0.75)
            ax.scatter(points, ticks, label=label, marker=marker, color=color, s=18, zorder=3)
        ax.set_yticks(range(len(CASES)), CASE_LABELS if panel == 0 else [])
        ax.set_ylim(3.5, -0.5)
        ax.axvline(0, color="#526170", linestyle="--", linewidth=0.7)
        ax.set_xlabel(xlabel, fontsize=8.2)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.tick_params(axis="both", labelsize=8)
        y_grid(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    figure_legend(fig, handles, labels, columns=2)
    save(fig, out, "08_expansion_paired_effects")


def traffic_figure(groups, out):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.15), layout="constrained")
    metrics = (
        ("control_body_bytes_per_released", "（a）控制消息体"),
        ("data_body_bytes_per_released", "（b）业务数据体"),
    )
    for ax, (key, title) in zip(axes, metrics):
        for method, label, color, offset in zip(
            METHODS, METHOD_LABELS, METHOD_COLORS, (-0.25, 0, 0.25)
        ):
            amounts = [groups[case][method]["cost"][key] / 1024 for case in CASES]
            ax.bar([i + offset for i in range(len(CASES))], amounts, width=0.22,
                   color=color, label=label)
        ax.set_xticks(range(len(CASES)), CASE_LABELS)
        ax.set_ylabel("KiB/释放任务")
        ax.set_title(title, loc="left")
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        y_grid(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    figure_legend(fig, handles, labels, columns=3)
    save(fig, out, "09_expansion_traffic")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, type=Path, help="Audited expansion results")
    parser.add_argument("--out", required=True, type=Path, help="New figure output directory")
    args = parser.parse_args()
    font = configure()
    summary = read_json(args.summary)
    groups = arm_groups(summary)
    args.out.mkdir(parents=True, exist_ok=True)
    delivery_figure(groups, args.out)
    paired_effect_figure(summary["contrasts"], args.out)
    traffic_figure(groups, args.out)
    print(f"Three 600-DPI PNG and vector PDF figure pairs written using {font}.")


if __name__ == "__main__":
    main()
