"""Summarize the recorded INDEX-GATE-01 replay and verify gate coverage."""

import csv
import json
import math
import statistics
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
K_VALUES = (10, 50, 100, 500)
BUDGETS = (100, 500, 5000)
VARIANTS = ("flat", "contract", "generic")
QUERY_METRICS = (
    "full_conditioned_count", "all_internal_nodes", "internal_nodes_visited", "leaves_visited",
    "leaf_ids_inspected", "node_bound_evaluations", "metadata_records_touched", "metadata_passes",
    "complete_candidates_touched", "exact_public_scores", "capability_rejects", "depth_rejects",
    "bound_pruned_candidates", "touch_ratio", "node_visit_ratio", "returned_k",
    "query_setup_s", "node_bound_s", "traversal_s", "candidate_scoring_s", "flat_feature_s",
    "total_public_search_s", "peak_working_set_bytes",
)
AGREEMENT_METRICS = (
    "public_search_s", "query_setup_s", "node_bound_s", "traversal_s", "candidate_scoring_s", "flat_feature_s",
    "exact_verification_s", "negotiation_s", "reconstruction_s", "total_method_s",
    "complete_candidates_touched", "exact_public_scores", "verification_calls",
)


def read_csv(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else default


def truth(value):
    if value in (True, "1", "true", "True", "PASS"):
        return True
    if value in (False, "0", "false", "False", "FAIL"):
        return False
    raise ValueError(f"Invalid boolean field {value!r}")


def records_by_key(rows, limit_field):
    keys = {}
    for row in rows:
        key = (row["instance_id"], row["variant"], int(row[limit_field]))
        if key in keys:
            raise ValueError(f"Duplicate replay row {key!r}")
        keys[key] = row
    return keys


def quantile(numbers, probability):
    values = sorted(numbers)
    offset = (len(values) - 1) * probability
    low, high = math.floor(offset), math.ceil(offset)
    return values[low] + (values[high] - values[low]) * (offset - low)


def finite_values(rows, field):
    result = []
    for row in rows:
        if row.get(field) in ("", None):
            continue
        value = float(row[field])
        if not math.isfinite(value):
            raise ValueError(f"Non-finite metric {field!r}")
        result.append(value)
    return result


def summarize(rows, metrics, *, experiment, cohort, variant, checkpoint):
    output = []
    for metric in metrics:
        values = finite_values(rows, metric)
        if values:
            output.append(dict(
                experiment=experiment, cohort=cohort, variant=variant, checkpoint=checkpoint,
                metric=metric, n=len(values), median=quantile(values, 0.5),
                p90=quantile(values, 0.90), p95=quantile(values, 0.95),
                mean=statistics.fmean(values),
            ))
    return output


def cohort_sets():
    historical = read_csv(ROOT / "results" / "flat_audit" / "per_instance.csv")
    by_id = {row["instance_id"]: row for row in historical}
    if len(by_id) != len(historical) or len(by_id) != 1920:
        raise ValueError("Expected 1,920 unique historical instances")
    plan = read_json(ROOT / "PILOT01_PLAN_TEMPLATE.json")["instances"]
    fixed = {row["instance_id"] for row in plan if row["seed_index"] == 0}
    target = {key for key, r in by_id.items() if truth(r["target_b2_no_full_o1_yes"])}
    large = {key for key in target
             if int(by_id[key]["conditioned_structural_method_eligible"]) >= 100_000}
    rich = {key for key in target
            if by_id[key]["capability_richness"] == "rich" and by_id[key]["composition_depth"] == "2"}
    if tuple(map(len, (target, large, rich, fixed, target & fixed))) != (842, 340, 298, 96, 37):
        raise ValueError("Historical audit and template disagree with expected cohorts")
    return by_id, {"target": target, "large": large, "rich_depth2": rich, "fixed_grid": fixed}


def check_query_rows(queries, historical):
    for key, row in queries.items():
        instance_id, variant, k = key
        original = historical[instance_id]
        n = int(original["conditioned_structural_method_eligible"])
        if k not in K_VALUES or variant not in VARIANTS or n != int(row["full_conditioned_count"]):
            raise ValueError(f"Invalid candidate domain or query key {key!r}")
        labels = {
            "family": "family", "depth": "composition_depth", "richness": "capability_richness",
            "pressure": "resource_pressure", "conflict": "preference_conflict",
        }
        if any(row[field] != original[old] for field, old in labels.items()):
            raise ValueError(f"Query identity labels differ from the historical record for {key!r}")
        touched, scored = int(row["complete_candidates_touched"]), int(row["exact_public_scores"])
        if not 0 <= scored <= touched:
            raise ValueError(f"Candidate touch and scoring counts disagree for {key!r}")
        if int(row["returned_k"]) != min(n, k):
            raise ValueError(f"Unexpected returned candidate count for {key!r}")
        if n and not math.isclose(float(row["touch_ratio"]), touched / n, rel_tol=1e-6, abs_tol=1e-12):
            raise ValueError(f"Invalid candidate touch ratio for {key!r}")
        all_nodes = row.get("all_internal_nodes")
        if variant != "flat" and all_nodes not in ("", None) and int(all_nodes) > 0:
            ratio = int(row["internal_nodes_visited"]) / int(all_nodes)
            if not math.isclose(float(row["node_visit_ratio"]), ratio, rel_tol=1e-6, abs_tol=1e-12):
                raise ValueError(f"Invalid internal-node visit ratio for {key!r}")


def correctness_status(checks, queries, cohorts):
    cover = []
    failures = []
    for variant in ("contract", "generic"):
        for cohort in ("fixed_grid", "target"):
            for k in K_VALUES:
                keys = {(key, variant, k) for key in cohorts[cohort]}
                available = keys.intersection(checks).intersection(queries)
                failed = [key for key in sorted(available) if
                          not all(truth(checks[key][name]) for name in
                                  ("ids_equal", "order_equal", "scores_bitwise_equal")) or
                          int(checks[key]["expected_k"]) != int(checks[key]["returned_k"]) or
                          int(checks[key]["returned_k"]) != int(queries[key]["returned_k"])]
                cover.append(dict(variant=variant, cohort=cohort, k=k, expected=len(keys),
                                  compared=len(available), failed=len(failed)))
                failures.extend(failed)
    primary = [row for row in cover if row["variant"] == "contract"]
    return all(row["compared"] == row["expected"] for row in primary) and not failures, cover, sorted(set(failures))


def equivalent_values(first, second):
    if truth(first["agreement"]) != truth(second["agreement"]):
        return False
    for field in ("class_id", "representative", "uA", "uN", "nash", "verification_calls"):
        if first[field] != second[field]:
            return False
    return True


def agreement_status(agreements, target):
    coverage = []
    failures = []
    for budget in BUDGETS:
        compared = [key for key in sorted(target)
                    if {(key, "flat", budget), (key, "contract", budget)} <= agreements.keys()]
        for key in compared:
            first = agreements[key, "flat", budget]
            second = agreements[key, "contract", budget]
            if (not equivalent_values(first, second) or not truth(first["original_match"])
                    or not truth(second["original_match"]) or not truth(first["history_match"])
                    or not truth(second["history_match"])):
                failures.append((key, budget))
        coverage.append(dict(budget=budget, expected=len(target), compared=len(compared),
                             failed=sum(b == budget for _, b in failures)))
    return all(r["expected"] == r["compared"] and r["failed"] == 0 for r in coverage), coverage, failures


def choose(rows, ids, variant, checkpoint):
    return [row for (identifier, method, k), row in rows.items()
            if identifier in ids and method == variant and k == checkpoint]


def paired_summary(queries, ids, variant, k=500):
    paired = sorted(key for key in ids if (key, "flat", k) in queries and
                    (key, variant, k) in queries)
    if not paired:
        return dict(n=0, expected=len(ids))
    flat = [float(queries[key, "flat", k]["total_public_search_s"]) for key in paired]
    indexed = [float(queries[key, variant, k]["total_public_search_s"]) for key in paired]
    by_index = [queries[key, variant, k] for key in paired]
    touch = [float(row["touch_ratio"]) for row in by_index]
    result = dict(
        n=len(paired), expected=len(ids),
        flat_median=quantile(flat, 0.5), flat_p95=quantile(flat, 0.95),
        index_median=quantile(indexed, 0.5), index_p95=quantile(indexed, 0.95),
        p95_reduction_percent=100 * (1 - quantile(indexed, 0.95) / quantile(flat, 0.95)),
        touch_median=quantile(touch, 0.5), touch_p95=quantile(touch, 0.95),
        touch_le_005=sum(x <= 0.05 for x in touch),
        touch_le_001=sum(x <= 0.01 for x in touch),
    )
    for field in ("internal_nodes_visited", "node_visit_ratio", "exact_public_scores"):
        values = finite_values(by_index, field)
        if values:
            result[field + "_median"] = quantile(values, 0.5)
            result[field + "_p95"] = quantile(values, 0.95)
    return result


def paired_agreement_runtime(agreements, ids):
    checkpoint = 5000
    paired = sorted(key for key in ids if (key, "flat", checkpoint) in agreements and
                    (key, "contract", checkpoint) in agreements)
    output = dict(n=len(paired), expected=len(ids))
    if paired:
        for field in ("public_search_s", "total_method_s"):
            flat = [float(agreements[key, "flat", checkpoint][field]) for key in paired]
            indexed = [float(agreements[key, "contract", checkpoint][field]) for key in paired]
            output[field] = dict(
                flat_median=quantile(flat, 0.5), flat_p95=quantile(flat, 0.95),
                index_median=quantile(indexed, 0.5), index_p95=quantile(indexed, 0.95),
                p95_reduction_percent=100 * (1 - quantile(indexed, 0.95) / quantile(flat, 0.95)),
            )
    return output


def table(headers, rows):
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(map(str, row)) + " |" for row in rows),
    ]


def report(path, lines):
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def gate_label(ok, coverage_ok):
    return "PASS" if ok else "FAIL" if coverage_ok else "INCOMPLETE"


def runtime_rows(queries, agreements, cohorts):
    for cohort, ids in cohorts.items():
        for variant in VARIANTS:
            for k in K_VALUES:
                selected = choose(queries, ids, variant, k)
                yield from summarize(selected, QUERY_METRICS, experiment="topk", cohort=cohort,
                                     variant=variant, checkpoint=k)
        for variant in ("flat", "contract"):
            for budget in BUDGETS:
                selected = choose(agreements, ids, variant, budget)
                yield from summarize(selected, AGREEMENT_METRICS, experiment="agreement",
                                     cohort=cohort, variant=variant, checkpoint=budget)


def query_runtime_lines(pairs, agreement_pairs, summary):
    lines = [
        "# INDEX-GATE-01 runtime",
        "",
        "The table compares paired public search at K=500 on existing serialized instances. "
        "The FLAT measurement includes its complete conditioning, scoring and sorting. "
        "The retrieval measurement includes setup, node bounds, traversal and candidate scoring. "
        "The main replay runs serially within one worker and uses the same warm public graph. "
        "Graph and index build and load are accounted for separately. Preliminary engineering checks "
        "are outside these timing summaries.",
        "",
    ]
    rows = []
    for cohort in ("target", "large", "rich_depth2"):
        values = pairs["contract"][cohort]
        n = values["n"]
        timing = ("—", "—", "—")
        if n:
            timing = (f'{values["flat_median"]:.6f} / {values["flat_p95"]:.6f}',
                      f'{values["index_median"]:.6f} / {values["index_p95"]:.6f}',
                      f'{values["p95_reduction_percent"]:.2f}%')
        rows.append((cohort, f'{n}/{values["expected"]}', *timing))
    lines += table(("Cohort", "Paired n", "FLAT median / p95 s",
                    "Contract median / p95 s", "p95 reduction"), rows)
    lines += ["", "The gate uses 100 × (1 − indexed p95 / FLAT p95) for the same large-cohort IDs. "
              "Each quantile uses linear interpolation. The runtime CSV also records the mean and p90.", ""]
    lines += ["## Agreement replay at B=5,000", "",
              "The indexed method extends the prefix only as verification asks for more candidates. "
              "These paired method timings use the actual stopping points.", ""]
    rows = []
    for cohort in ("target", "large", "rich_depth2"):
        values = agreement_pairs[cohort]
        for field in ("public_search_s", "total_method_s"):
            q = values.get(field)
            timing = ("—", "—", "—") if q is None else (
                f'{q["flat_median"]:.6f} / {q["flat_p95"]:.6f}',
                f'{q["index_median"]:.6f} / {q["index_p95"]:.6f}', f'{q["p95_reduction_percent"]:.2f}%',
            )
            rows.append((cohort, field, f'{values["n"]}/{values["expected"]}', *timing))
    lines += table(("Cohort", "Phase", "Paired n", "FLAT median / p95 s",
                    "Contract median / p95 s", "p95 reduction"), rows)
    lines.append("")
    for experiment, checkpoint, metrics in (
        ("topk", 500, ("query_setup_s", "node_bound_s", "traversal_s", "candidate_scoring_s", "flat_feature_s",
                        "total_public_search_s")),
        ("agreement", 5000, AGREEMENT_METRICS[:10]),
    ):
        lines.extend([f"## {experiment} at {checkpoint}", ""])
        rows = [(r["cohort"], r["variant"], r["metric"], r["n"], f'{r["median"]:.6f}',
                 f'{r["p90"]:.6f}', f'{r["p95"]:.6f}', f'{r["mean"]:.6f}')
                for r in summary if r["experiment"] == experiment and r["checkpoint"] == checkpoint
                and r["metric"] in metrics and r["cohort"] != "fixed_grid"]
        lines += table(("Cohort", "Variant", "Phase", "n", "Median s",
                        "p90 s", "p95 s", "Mean s"), rows)
        lines.append("")
    lines += ["FLAT's `flat_feature_s` records its original proxy feature calculation. "
              "The full FLAT plan time also includes its scalar score combination and complete sort. "
              "For fixed-K indexed rows, the cursor setup phase is reported separately from other "
              "setup included in the total, such as the public view and static lookup. "
              "The agreement replay includes candidate retrieval, exact verification, "
              "negotiation and reconstruction at the recorded checkpoints. "
              "The two experiment types have separate timing boundaries and CSV entries. "
              "Use the raw rows to inspect phase totals and any overhead outside the named phases."]
    return lines


def generic_lines(pairs, metadata):
    lines = [
        "# Generic and contract-aware index comparison",
        "",
        "The generic tree partitions the same public feature vectors by axes. "
        "The contract-aware tree also partitions by legal capability and depth.",
        "",
    ]
    if metadata.get("comparison_description"):
        lines += [metadata["comparison_description"], ""]
    rows = []
    for variant in ("generic", "contract"):
        for cohort in ("target", "large", "rich_depth2"):
            values = pairs[variant][cohort]
            n = values["n"]
            metrics = ("—", "—", "—")
            if n:
                metrics = (f'{values["touch_median"]:.4%} / {values["touch_p95"]:.4%}',
                           f'{values["index_median"]:.6f} / {values["index_p95"]:.6f}',
                           f'{values["p95_reduction_percent"]:.2f}%')
            rows.append((variant, cohort, f'{n}/{values["expected"]}', *metrics))
    lines += table(("Variant", "K=500 cohort", "Paired with FLAT",
                    "TouchRatio median / p95", "Public search median / p95 s",
                    "p95 reduction vs FLAT"), rows)
    lines += ["", "Correctness coverage for each variant and each K is reported in "
              "`INDEX_CORRECTNESS_REPORT.md`. Timing summaries use the paired FLAT IDs for each row. "
              "Unequal cohort coverage precludes a direct variant speed comparison between those rows."]
    return lines


def correctness_lines(g1, g2, coverage, paths, mismatch, disagreement, unique, metadata):
    lines = [
        "# INDEX-GATE-01 exactness and agreement",
        "",
        f"- G1 contract top-K comparisons {g1}.",
        f"- G2 agreement-path equivalence {g2}.",
        "",
    ]
    if mismatch:
        lines += ["`INDEX_GATE_FAIL_CORRECTNESS` was observed in at least one measured comparison.", ""]
    lines += ["The fixed-grid selection uses existing seed-index 0 in every configuration. "
              "The target cohort has 842 instances. Thirty-seven belong to both sets. "
              "Each indexed result is checked for candidate IDs, order and exact binary64 score bits "
              "against the original FLAT score and tie-break.", "",
              f"The union contains 901 instances. The captured Top-K rows include {unique['contract']:,} "
              f"contract and {unique['generic']:,} generic comparisons out of 3,604 expected per variant. "
              "The two cohort views below share the 37 overlapping instances.", ""]
    lines += table(("Variant", "Cohort", "K", "Compared", "Expected", "Mismatches"),
                   [(r["variant"], r["cohort"], r["k"], r["compared"], r["expected"], r["failed"])
                    for r in coverage])
    lines += ["", "Agreement replay compares the common verifier and bilateral protocol outcomes, "
              "selected representative, uA, uN, Nash welfare, verification calls and the recorded "
              "protocol history. All target instances are required at each budget.", ""]
    lines += table(("Budget", "Paired target", "Expected", "Mismatches"),
                   [(r["budget"], r["compared"], r["expected"], r["failed"]) for r in paths])
    if mismatch or disagreement:
        lines += ["", "First failing keys", "", "```text",
                  *map(str, (mismatch + disagreement)[:20]), "```"]
    if metadata.get("correctness_description"):
        lines += ["", metadata["correctness_description"]]
    return lines


def cost_lines(pairs, build, metadata):
    lines = [
        "# INDEX-GATE-01 work and storage",
        "",
        "TouchRatio divides complete candidate records inspected by the original FLAT conditioned "
        "structural count. A metadata or node-bound check is tallied separately from a complete "
        "candidate record and an exact public score. NodeVisitRatio divides internal node visits "
        "by the internal node denominator recorded for that query. Pruned counts are reported "
        "with the counting boundary of the implementation.",
        "",
    ]
    if metadata.get("counting_description"):
        lines += [metadata["counting_description"], ""]
    rows = []
    for cohort in ("target", "large", "rich_depth2"):
        value = pairs["contract"][cohort]
        counts = ("—", "—", "—", "—", "—", "—")
        if value["n"]:
            n = value["n"]
            counts = (f'{value["touch_median"]:.4%} / {value["touch_p95"]:.4%}',
                      f'{value["touch_le_005"]}/{n} ({value["touch_le_005"] / n:.2%})',
                      f'{value["touch_le_001"]}/{n} ({value["touch_le_001"] / n:.2%})',
                      f'{value["internal_nodes_visited_median"]:,.2f} / {value["internal_nodes_visited_p95"]:,.2f}',
                      f'{value["node_visit_ratio_median"]:.4%} / {value["node_visit_ratio_p95"]:.4%}',
                      f'{value["exact_public_scores_median"]:,.2f} / {value["exact_public_scores_p95"]:,.2f}')
        rows.append((cohort, f'{value["n"]}/{value["expected"]}', *counts))
    lines += table(("Contract K=500 cohort", "Paired n", "TouchRatio median / p95",
                    "Coverage ≤5%", "Coverage ≤1%", "Internal visits median / p95",
                    "NodeVisitRatio median / p95", "Exact scores median / p95"), rows)
    lines += ["", "Internal-node visits, candidate touches, eligibility rejects, bound prunes, "
              "scores, returned counts and working-set measurements are in the query CSV. "
              "The median and p95 for each value are in the summary CSV. "
              "Working sets refer to the resident worker including the shared graph and both trees. "
              "The ticker samples running calls and measures their endpoints.", "",
              "## Public feature schema", "",
              "The index is versioned as `INDEX-GATE-01-public-tree-v1`. "
              "Array offsets are class IDs. For each class, the six uint8 cell codes index an "
              "immutable 55 × 3 binary64 RAN/FH/EDGE demand-basis table. The basis codes distinguish "
              "27 local profiles, 27 offloaded profiles and idle. Separate uint8 masks record "
              "active cells and offloaded cells. Binary64 arrays store FLAT's exact averaged quality "
              "and capability cost. Additional arrays store mechanism bits and group count, the required "
              "capability-role mask, the minimum rich derivable depth and exact availability bitsets "
              "for each query depth.", "",
              "Each node has a contiguous member range, child IDs, 18 demand minima and maxima, "
              "minimum capability cost, maximum quality, minimum group count and class ID, "
              "depth extrema and depth-1 count, and role and availability summaries. "
              "The on-disk manifest records source and per-array hashes. "
              "The standalone tree audit checks all nodes and all 17 × 2 availability/depth domains.", "",
              "## Offline measurements", ""]
    if build:
        offline = build.get("build", {})
        load = build.get("load", {})
        lines += ["The existing semantic graph was built in 198.097 s and serialized in "
                  "another 12.211 s. Its 7,464,460-byte compressed artifact and 358,879,232-byte "
                  "precompute process peak come from the historical semantic-library audit. "
                  "The following measurements describe the new index.", ""]
        if offline and load:
            availability = ROOT / "results" / "engineering" / "availability_indices"
            preexisting_availability_bytes = ((availability / "manifest.json").stat().st_size +
                                              sum(path.stat().st_size for path in availability.glob("availability_*.bin.gz")))
            lines += table(("Measurement", "Value"), (
                ("Index build and serialization, excluding graph boot", f'{offline["index_build_s"]:.6f} s'),
                ("Peak process working set during index build", f'{offline["peak_build_working_set_bytes"]:,} B'),
                ("Shared feature arrays", f'{offline["shared_bytes"]:,} B'),
                ("Full index artifact including both variants and manifest", f'{offline["index_bytes_total"]:,} B'),
                ("Compressed graph plus both variants", f'{offline["graph_plus_index_bytes"]:,} B'),
                ("Existing availability artifacts, separately", f'{preexisting_availability_bytes:,} B'),
                ("Graph, index and existing availability artifacts",
                 f'{offline["graph_plus_index_bytes"] + preexisting_availability_bytes:,} B'),
                ("Index load and integrity checks, excluding graph boot", f'{load["index_load_s"]:.6f} s'),
            ))
            lines += [""]
            rows = [(name, detail["roots"], detail["nodes"], detail["leaves"],
                     f'{detail["build_s"]:.6f}', f'{detail["serialized_bytes"]:,}',
                     f'{offline["graph_bytes"] + offline["shared_bytes"] + detail["serialized_bytes"]:,}')
                    for name, detail in offline["trees"].items()]
            lines += table(("Variant", "Roots", "Nodes", "Leaves", "Tree build s", "Tree bytes",
                            "Graph plus shared arrays plus this tree bytes"), rows)
            lines += ["", "Per-variant storage sums exclude the manifest. "
                      "The raw metadata includes the separate graph/index boot timings.", ""]
        lines += ["```json", json.dumps(build, indent=2), "```"]
    else:
        lines += ["Index build and load measurements are pending."]
    return lines


def compute_gate(correct, correct_coverage, agreement, path_coverage, pairs, g5):
    correct_covered = all(r["expected"] == r["compared"] for r in correct_coverage
                          if r["variant"] == "contract")
    agreement_covered = all(r["expected"] == r["compared"] for r in path_coverage)
    rich, large = (pairs["contract"][c] for c in ("rich_depth2", "large"))
    g3_covered = rich["n"] == rich["expected"]
    g4_covered = large["n"] == large["expected"]
    g3 = g3_covered and rich["touch_p95"] <= 0.10
    g4 = g4_covered and large["p95_reduction_percent"] >= 30
    gates = {"G1": gate_label(correct, correct_covered or any(r["failed"] for r in correct_coverage)),
             "G2": gate_label(agreement, agreement_covered or any(r["failed"] for r in path_coverage)),
             "G3": gate_label(g3, g3_covered), "G4": gate_label(g4, g4_covered), "G5": g5}
    if any(gates[g] == "FAIL" for g in ("G1", "G2", "G5")):
        status = "FAIL_BOUND"
    elif "INCOMPLETE" in gates.values():
        status = "INCOMPLETE"
    elif not g3:
        status = "FAIL_TOUCH"
    elif not g4:
        status = "FAIL_RUNTIME"
    else:
        status = "PASS"
    return gates, status


def gate_lines(gates, status, g5_evidence, preservation):
    lines = [
        "# INDEX-GATE-01",
        "",
        f"**{status}**",
        "",
        "The replay uses the existing serialized PILOT instances and the frozen 1,394,064-class "
        "semantic graph. It tests the feasibility of exact indexed retrieval of the original FLAT order.",
        "",
    ]
    lines += table(("Gate", "Result"), list(gates.items()))
    if gates["G1"] == "FAIL":
        lines += ["", "`INDEX_GATE_FAIL_CORRECTNESS` applies to the top-K mismatch."]
    if gates["G3"] == "PASS" and gates["G4"] == "FAIL":
        lines += ["", "`INDEX_COMPUTATION_OVERHEAD` applies because the index crossed the touch "
                  "threshold while missing the runtime threshold."]
    if status == "PASS":
        lines += ["", "The result supports proceeding to `ON-DEMAND-GRAMMAR-SEARCH-01` as the next "
                  "feasibility study. This gate evaluated retrieval from the existing depth-2 graph."]
    if g5_evidence:
        lines += ["", "## Public feature boundary", "", *("- " + text for text in g5_evidence)]
    if preservation:
        lines += ["", "## Preservation", "", preservation]
    lines += ["", "The correctness, candidate costs, runtime and generic-index differential are "
              "documented in the companion reports. Use the query and agreement CSVs for per-instance detail."]
    return lines


def main():
    historical, cohorts = cohort_sets()
    queries = records_by_key(read_csv(HERE / "per_query.csv"), "k")
    checks = records_by_key(read_csv(HERE / "topk_correctness.csv"), "k")
    agreements = records_by_key(read_csv(HERE / "agreement_paths.csv"), "budget")
    metadata = read_json(HERE / "report_metadata.json", {})
    build = {}
    for name in ("build", "load"):
        measurements = read_json(HERE / "index" / (name + "_metrics.json"))
        if measurements:
            build[name] = measurements
    check_query_rows(queries, historical)
    pairs = {variant: {cohort: paired_summary(queries, ids, variant)
                       for cohort, ids in cohorts.items()}
             for variant in ("contract", "generic")}
    correct, coverage, mismatch = correctness_status(checks, queries, cohorts)
    agreement, paths, disagreement = agreement_status(agreements, cohorts["target"])
    agreement_pairs = {cohort: paired_agreement_runtime(agreements, ids)
                       for cohort, ids in cohorts.items()}
    gates, status = compute_gate(correct, coverage, agreement, paths, pairs,
                                 metadata.get("g5_status", "INCOMPLETE"))
    summary = list(runtime_rows(queries, agreements, cohorts))
    fields = ("experiment", "cohort", "variant", "checkpoint", "metric", "n",
              "median", "p90", "p95", "mean")
    with (HERE / "runtime_summary.csv").open("w", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)
    report(ROOT / "INDEX_GATE_REPORT.md", gate_lines(gates, status,
           metadata.get("g5_evidence", []), metadata.get("preservation")))
    report(ROOT / "INDEX_CORRECTNESS_REPORT.md",
           correctness_lines(gates["G1"], gates["G2"], coverage, paths, mismatch, disagreement,
                             {variant: sum(key[1] == variant for key in checks)
                              for variant in ("contract", "generic")}, metadata))
    report(ROOT / "INDEX_COST_REPORT.md", cost_lines(pairs, build, metadata))
    report(ROOT / "INDEX_RUNTIME_REPORT.md", query_runtime_lines(pairs, agreement_pairs, summary))
    report(ROOT / "GENERIC_INDEX_COMPARISON.md", generic_lines(pairs, metadata))
    result = dict(gates=gates, status=status, cohorts={k: len(v) for k, v in cohorts.items()},
                  paired_k500=pairs, paired_agreements_b5000=agreement_pairs,
                  correctness=coverage, agreement=paths)
    report(HERE / "gate_summary.json", [json.dumps(result, indent=2)])
    print(json.dumps(dict(gates=gates, status=status, paired_k500=pairs), indent=2))


if __name__ == "__main__":
    main()
