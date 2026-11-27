"""Plot paired development attempts and ablation work from the per-query CSV."""

import argparse
from collections import Counter
import csv
from math import isfinite
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.colors import SymLogNorm
from matplotlib.lines import Line2D
import numpy as np


HERE = Path(__file__).resolve().parent
CURRENT = "CURRENT_ON_DEMAND_GRAMMAR_SEARCH"
GENERIC = "GENERIC_ABSTRACT_BEST_FIRST"
EXACT = frozenset(("EXACT_TOPK_FULL_LENGTH", "EXACT_DOMAIN_EXHAUSTED_SHORT"))
CAPPED = "NOT_CERTIFIED_WITHIN_BUDGET"
ABLATIONS = (
    ("NO_EARLY_SEMANTIC_DEDUP", "A1 Early semantic dedup"),
    ("GENERIC_BOUND_ONLY", "A2 Contract-specific bound"),
    ("DEFER_CAPABILITY_PRUNING", "A3 Early capability pruning"),
    ("WEAK_STATE_TIME_RESOURCE_ENVELOPE", "A4 Envelope precision"),
    ("NO_LAZY_STOP", "A5 Lazy stopping"),
    ("NO_SEARCH_TIME_DOMAIN_NORMALIZATION", "A6 Search-time normalization"),
)
COHORTS = (
    ("All", lambda row: True),
    ("High cost", lambda row: row["high_cost"] == "True"),
    ("Rich depth 2", lambda row: row["richness"] == "rich" and depth(row) == 2),
    ("Depth 3", lambda row: depth(row) == 3),
)
POINTS = {
    ("exact", "exact"): ("Both exact", "o", "#225a7c", True),
    ("exact", "limit"): ("Generic limited", "^", "#a74a20", False),
    ("limit", "exact"): ("Current limited", ">", "#73458a", False),
    ("limit", "limit"): ("Both limited", "s", "#525b61", False),
}


def depth(row):
    return int(row["effective_depth"])


def number(row, name):
    raw = row[name]
    if not raw:
        return None
    value = float(raw)
    if not isfinite(value):
        raise ValueError(f"Nonfinite {name} for {row['instance_id']}")
    return value


def load_queries(path):
    required = {"method", "instance_id", "effective_depth", "instance_hash", "k",
                "prefix_status", "delivery_status", "high_cost", "richness",
                "online_elapsed_s", "partial_nodes_expanded"}
    by_query = {}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing input fields: {sorted(missing)}")
        for row in reader:
            if row["k"] != "500":
                continue
            query = row["instance_id"], depth(row)
            methods = by_query.setdefault(query, {})
            if row["method"] in methods:
                raise ValueError(f"Duplicate K=500 method row: {query}, {row['method']}")
            methods[row["method"]] = row
    if not by_query or any(CURRENT not in methods for methods in by_query.values()):
        raise ValueError("K=500 current-search plan rows missing")
    for query, methods in by_query.items():
        identities = {row["instance_hash"] for row in methods.values() if row["instance_hash"]}
        if len(identities) > 1:
            raise ValueError(f"Unpaired instance hashes for {query}")
    return list(by_query.values())


def status(row):
    if row["delivery_status"] in EXACT:
        return "exact"
    if row["delivery_status"] == CAPPED:
        return "limit"
    return "missing"


def paired_latency(queries, path):
    fig, axes = plt.subplots(1, 2, figsize=(9.1, 4.7))
    for ax, group, label in zip(axes, (False, True), ("Original depth ≤2", "Depth 3")):
        sample = [m for m in queries if (depth(m[CURRENT]) == 3) == group]
        pairs = {category: [] for category in POINTS}
        omitted = 0
        for methods in sample:
            original, generic = methods[CURRENT], methods.get(GENERIC)
            if not generic:
                omitted += 1
                continue
            category = status(original), status(generic)
            left, right = number(original, "online_elapsed_s"), number(generic, "online_elapsed_s")
            if category not in pairs or left is None or right is None or min(left, right) <= 0:
                omitted += 1
                continue
            pairs[category].append((left, right))
        plotted = [x for values in pairs.values() for pair in values for x in pair]
        if plotted:
            low, high = min(plotted) / 1.35, max(plotted) * 1.30
            ax.plot((low, high), (low, high), color="#86939c", ls="--", lw=1, zorder=1)
            ax.set(xlim=(low, high), ylim=(low, high), xscale="log", yscale="log")
            ax.set_aspect("equal", adjustable="box")
            for category, xy in pairs.items():
                if xy:
                    _, marker, color, filled = POINTS[category]
                    x, y = zip(*xy)
                    ax.scatter(x, y, marker=marker, s=28, facecolors=color if filled else "none",
                               edgecolors=color, linewidths=0.9, alpha=0.78, zorder=3)
            ax.grid(which="major", color="#e4e9ec", lw=0.7)
        else:
            ax.set(xticks=[], yticks=[])
            ax.text(0.5, 0.5, "No comparable attempt times", transform=ax.transAxes,
                    ha="center", va="center", color="#525b61")
        exact = len(pairs["exact", "exact"])
        ax.set_title(f"{label} · {len(sample)} planned pairs\n"
                     f"{exact} co-certified · {omitted} unavailable", fontsize=10.5)
        ax.set_xlabel("Current search elapsed seconds")
    axes[0].set_ylabel("Generic best-first elapsed seconds")
    fig.suptitle("Paired K=500 public-search attempts", fontsize=13, fontweight="semibold")
    handles = [
        Line2D([0], [0], linestyle="", marker=marker, color=color,
               markerfacecolor=color if filled else "none", markersize=5.5, label=label)
        for label, marker, color, filled in POINTS.values()
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8.5, frameon=False)
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.20, top=0.80, wspace=0.36)
    fig.savefig(path, dpi=165, facecolor="white")
    plt.close(fig)


def ablation_stats(queries):
    deltas = np.full((len(ABLATIONS), len(COHORTS)), np.nan)
    coverage = np.full_like(deltas, np.nan)
    work_text, coverage_text = [], []
    for row_index, (arm, _) in enumerate(ABLATIONS):
        work_labels, coverage_labels = [], []
        for col_index, (_, include) in enumerate(COHORTS):
            cohort = [methods for methods in queries if include(methods[CURRENT])]
            measured, delivered, prefix_exact = [], 0, 0
            for methods in cohort:
                variant = methods.get(arm)
                if not variant:
                    continue
                original = methods[CURRENT]
                exact = variant["delivery_status"] in EXACT
                delivered += exact
                prefix_exact += variant["prefix_status"] in EXACT
                if exact and original["delivery_status"] in EXACT:
                    left = number(original, "partial_nodes_expanded")
                    right = number(variant, "partial_nodes_expanded")
                    if left is not None and right is not None:
                        measured.append(right - left)
            if measured:
                delta = median(measured)
                deltas[row_index, col_index] = delta
                work_labels.append(f"{delta:+,.1f}\nn={len(measured)}")
            else:
                work_labels.append("NA\nn=0")
            count = len(cohort)
            if count:
                coverage[row_index, col_index] = delivered / count
            coverage_labels.append(f"{delivered}/{count}" + (
                f"\n{prefix_exact} proofs" if prefix_exact != delivered else ""
            ))
        work_text.append(work_labels)
        coverage_text.append(coverage_labels)
    return deltas, coverage, work_text, coverage_text


def label_cells(ax, values, labels, text_color):
    for y, labels_at_row in enumerate(labels):
        for x, label in enumerate(labels_at_row):
            ax.text(x, y, label, ha="center", va="center", fontsize=8.2,
                    color=text_color(values[y, x]))


def ablation_work_coverage(queries, path):
    work, coverage, work_text, coverage_text = ablation_stats(queries)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.65), gridspec_kw={"width_ratios": (1.1, 1)})
    left, right = axes
    finite = np.abs(work[np.isfinite(work)])
    magnitude = max(float(finite.max()) if finite.size else 0, 1)
    norm = SymLogNorm(linthresh=1, vmin=-magnitude, vmax=magnitude)
    cmap = plt.get_cmap("RdBu_r").with_extremes(bad="#f1f2f4")
    left.imshow(work, norm=norm, cmap=cmap, aspect="auto")
    right.imshow(coverage, vmin=0, vmax=1, cmap=plt.get_cmap("Blues"), aspect="auto")
    label_cells(left, work, work_text,
                lambda value: "white" if isfinite(value) and abs(norm(value) - 0.5) > 0.30 else "#172029")
    label_cells(right, coverage, coverage_text,
                lambda value: "white" if isfinite(value) and value > 0.66 else "#172029")
    for ax in axes:
        ax.set(xticks=range(len(COHORTS)), xticklabels=[name for name, _ in COHORTS],
               yticks=range(len(ABLATIONS)))
        ax.tick_params(left=False, bottom=False, labelsize=8.7)
        for spine in ax.spines.values():
            spine.set_visible(False)
    left.set_yticklabels([label for _, label in ABLATIONS])
    right.set_yticklabels([])
    left.set_title("Median paired Δ partial expansions\nAblation minus current · exact deliveries", fontsize=10.5)
    right.set_title("Exact delivery coverage\nDelivered / planned K=500 queries", fontsize=10.5)
    fig.suptitle("Single-factor ablations on the frozen development panel", fontsize=13, fontweight="semibold")
    fig.text(0.25, 0.035, "Positive Δ indicates more work. n counts matched exact deliveries.",
             fontsize=8.5, color="#3b4952")
    fig.subplots_adjust(left=0.23, right=0.98, bottom=0.13, top=0.77, wspace=0.13)
    fig.savefig(path, dpi=165, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=HERE / "per_query.csv")
    parser.add_argument("--output", type=Path, default=HERE / "figures")
    args = parser.parse_args()
    queries = load_queries(args.csv)
    args.output.mkdir(parents=True, exist_ok=True)
    paired_latency(queries, args.output / "paired_latency.png")
    ablation_work_coverage(queries, args.output / "ablation_work_coverage.png")


if __name__ == "__main__":
    main()
