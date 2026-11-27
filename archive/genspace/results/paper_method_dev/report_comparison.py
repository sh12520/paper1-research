"""Produce the paired development evidence bundle from the sealed attempts."""

from collections import Counter
from pathlib import Path
from statistics import median
import csv
import json
import math

from run_comparison import (ABLATIONS, ARCHIVE, CAPPED, CURRENT, FULL, GENERIC, GRAPH_METHODS,
                            HERE, KS, LIMITS, METHODS, ROOT, SHORT, UNSOUND, hash_file, read_json)
from audit_common import quantile


EXACT = frozenset((FULL, SHORT))
MEASURES = (
    "proof_elapsed_s", "online_elapsed_s", "operational_elapsed_s",
    "partial_nodes_generated", "partial_nodes_expanded", "partial_refinements_excluding_partition_probes",
    "unique_semantic_states", "complete_assignments_examined", "witness_asts_materialized",
    "raw_asts_materialized", "exact_public_scores", "bound_evaluations", "frontier_peak",
    "peak_rss_mib", "partition_probes", "early_semantic_merges", "terminal_duplicates",
    "deferred_capability_rejects", "coarsened_envelopes", "index_internal_nodes", "index_leaves",
    "packed_records_touched", "flat_metadata_records_touched", "post_proof_search_elapsed_s",
    "post_proof_partial_expanded",
)
FIELDS = (
    "instance_id", "effective_depth", "family", "pressure", "conflict", "richness", "method",
    "k", "prefix_status", "delivery_status", "correctness", "returned", "limit_reason",
    "instance_hash", "public_hash", "conditioned_candidates", "high_cost",
    "prefix_sha256", "witness_sha256", "protocol_status", "protocol_prefix_match",
    "protocol_budget_max", "agreement", "representative", "uA", "uN", "nash",
    "verification_calls", "proposals", "protocol_history_events", "startup_rss_mib",
    "process_lifetime_peak_rss_mib", "worker_pid", "memory_available_mib", *MEASURES,
)


def distribution(values):
    numbers = [x for x in values if x is not None]
    return (median(numbers), quantile(numbers, .95), max(numbers)) if numbers else (None,) * 3


def fmt(value):
    return "—" if value is None else f"{value:,.4g}"


def tabular(fields, rows):
    return "\n".join((
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
        *("| " + " | ".join(str(x) for x in row) + " |" for row in rows),
    ))


def write_csv(name, fields, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(name, *parts):
    (ROOT / name).write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def work_columns(attempt, cut, depth, at_last_k):
    # The ordinary method stops at the maximum K. A5 continues through the
    # same cursor, so its final work and earlier proof counters are both saved.
    stats = attempt.get("metrics", {}) if at_last_k else cut.get("metrics", {})
    before = cut.get("metrics", {})
    elapsed = attempt.get("elapsed_s") if at_last_k else cut.get("elapsed_s")
    valid = attempt.get("correctness") != UNSOUND
    proof = cut.get("elapsed_s") if cut.get("status") in EXACT and valid else None
    later = elapsed - proof if elapsed is not None and proof is not None and at_last_k else None
    extra = (stats["partial_expanded"] - before["partial_expanded"]
             if later is not None and stats.get("partial_expanded") is not None
             and before.get("partial_expanded") is not None else None)
    peak = attempt.get("query_sampled_peak_rss_bytes") if at_last_k else stats.get("peak_working_set_bytes")
    delivered = attempt.get("delivery_status") if at_last_k else cut.get("status")
    operational = None if not valid else (
        elapsed if delivered in EXACT else LIMITS[depth].wall_seconds if delivered == CAPPED else None)
    shape, assignment = stats.get("shape_nodes_expanded"), stats.get("assignment_nodes_expanded")
    refinements = (shape + assignment if shape is not None and assignment is not None
                   else stats.get("partial_expanded") if attempt["method"] == GENERIC else None)
    return dict(
        online_elapsed_s=elapsed, proof_elapsed_s=proof, operational_elapsed_s=operational,
        partial_nodes_generated=stats.get("partial_generated"), partial_nodes_expanded=stats.get("partial_expanded"),
        partial_refinements_excluding_partition_probes=refinements,
        unique_semantic_states=stats.get("unique_semantics"),
        complete_assignments_examined=(None if attempt["method"] in GRAPH_METHODS else stats.get("complete_syntax")),
        witness_asts_materialized=(stats.get("normalized_witnesses") if attempt["method"] == GENERIC
                                   else stats.get("witness_asts_materialized")),
        raw_asts_materialized=(stats.get("witness_asts_materialized") if attempt["method"] == GENERIC
                               else stats.get("raw_asts_materialized")),
        exact_public_scores=stats.get("scores"), bound_evaluations=stats.get("lower_bound_evaluations"),
        frontier_peak=stats.get("frontier_peak"), peak_rss_mib=peak / (1 << 20) if peak is not None else None,
        partition_probes=stats.get("partition_probes"), early_semantic_merges=stats.get("duplicate_states_eliminated"),
        terminal_duplicates=stats.get("terminal_duplicates", stats.get("duplicates")),
        deferred_capability_rejects=stats.get("deferred_capability_rejects"),
        coarsened_envelopes=stats.get("coarsened_envelopes"),
        index_internal_nodes=stats.get("index_internal_nodes_visited"),
        index_leaves=stats.get("index_leaf_nodes_visited"),
        packed_records_touched=stats.get("complete_candidates_touched"),
        flat_metadata_records_touched=stats.get("flat_metadata_records_touched"),
        post_proof_search_elapsed_s=later, post_proof_partial_expanded=extra,
    )


def flatten(plan):
    attempts = []
    rows = []
    for ident, depth in plan["query_order"]:
        family, pressure, conflict, richness, _, _ = ident.split("__")
        for method in plan["method_orders"][str(depth)]:
            path = HERE / "attempts" / f"{depth}__{ident}__{method}.json"
            attempt = read_json(path) if path.exists() else dict(method=method, correctness="NOT_RUN")
            attempts.append(attempt)
            protocol = attempt.get("protocol", {})
            budget = protocol.get("budget_max")
            outcome = protocol.get("outcomes", {}).get(str(budget), {})
            correctness = attempt["correctness"]
            for k in KS[depth]:
                final = k == 500
                cut = attempt.get("cuts", {}).get(str(k), {})
                status = UNSOUND if correctness == UNSOUND else cut.get("status", correctness)
                rows.append({
                    "instance_id": ident, "effective_depth": depth, "family": family, "pressure": pressure,
                    "conflict": conflict, "richness": richness, "method": method, "k": k,
                    "prefix_status": status, "delivery_status": (
                        UNSOUND if correctness == UNSOUND else attempt.get("delivery_status") if final else status),
                    "correctness": correctness, "returned": cut.get("returned"),
                    "limit_reason": cut.get("reason") or attempt.get("limit_reason"),
                    "instance_hash": attempt.get("instance_hash"), "public_hash": attempt.get("public_hash"),
                    "conditioned_candidates": plan["public_conditioned_counts"].get(ident) if depth < 3 else None,
                    "high_cost": depth < 3 and ident in plan["high_cost_ids"],
                    "prefix_sha256": cut.get("prefix_sha256"),
                    "witness_sha256": attempt.get("observed_witness_sha256") if final else None,
                    "protocol_status": protocol.get("status"),
                    "protocol_prefix_match": attempt.get("protocol_prefix_match"),
                    "protocol_budget_max": budget, "agreement": outcome.get("agreement"),
                    "representative": outcome.get("representative"), "uA": outcome.get("uA"),
                    "uN": outcome.get("uN"), "nash": outcome.get("nash"),
                    "verification_calls": outcome.get("verification_calls"), "proposals": outcome.get("proposals"),
                    "protocol_history_events": len(protocol["history"]) if protocol else None,
                    "worker_pid": attempt.get("worker_pid"), "memory_available_mib": attempt.get("memory_available_mib"),
                    "startup_rss_mib": attempt["baseline_rss_bytes"] / (1 << 20) if "baseline_rss_bytes" in attempt else None,
                    "process_lifetime_peak_rss_mib": attempt["process_lifetime_peak_rss_bytes"] / (1 << 20)
                    if "process_lifetime_peak_rss_bytes" in attempt else None,
                    **work_columns(attempt, cut, depth, final),
                })
    return attempts, rows


def selections(rows):
    return {
        "all_development": rows,
        "depth_le_2": [r for r in rows if r["effective_depth"] < 3],
        "high_cost": [r for r in rows if r["high_cost"]],
        "rich_depth2": [r for r in rows if r["richness"] == "rich" and r["effective_depth"] == 2],
        "sparse": [r for r in rows if r["richness"] == "sparse"],
        "depth3": [r for r in rows if r["effective_depth"] == 3],
    }


def summarize(cohorts):
    summaries = []
    for cohort, attempts in cohorts.items():
        base = {(r["instance_id"], r["effective_depth"]): r for r in attempts if r["method"] == CURRENT}
        for method in METHODS:
            ranked = [r for r in attempts if r["method"] == method]
            if not ranked:
                continue
            paired = [(base[(r["instance_id"], r["effective_depth"])], r) for r in ranked]
            prefix = Counter(r["prefix_status"] for r in ranked)
            comparisons = [(left, right) for left, right in paired
                           if left["delivery_status"] in EXACT and right["delivery_status"] in EXACT]
            proof_pairs = [(left, right) for left, right in paired
                           if left["prefix_status"] in EXACT and right["prefix_status"] in EXACT]
            reason = Counter(r["limit_reason"] for r in ranked if r["delivery_status"] == CAPPED)
            row = dict(cohort=cohort, method=method, planned_n=len(ranked),
                       full_n=prefix[FULL], short_n=prefix[SHORT], not_certified_n=prefix[CAPPED],
                       unsound_n=prefix[UNSOUND], skipped_n=prefix["STOPPED_AFTER_UNSOUND"] + prefix["NOT_RUN"],
                       exact_delivery_n=sum(r["delivery_status"] in EXACT for r in ranked),
                       shared_exact_delivery_n=len(comparisons), shared_exact_proof_n=len(proof_pairs),
                       limit_reasons=json.dumps(reason, sort_keys=True))
            row["paired_first_proof_delta_median_s"] = (
                median(r["proof_elapsed_s"] - l["proof_elapsed_s"] for l, r in proof_pairs) if proof_pairs else None)
            for status, label in ((EXACT, "delivered"), ({CAPPED}, "capped")):
                post_proof = [r for r in ranked if r["delivery_status"] in status
                              and r["post_proof_search_elapsed_s"] is not None]
                row[f"post_proof_{label}_n"] = len(post_proof)
                row[f"post_proof_{label}_median_s"] = (
                    median(r["post_proof_search_elapsed_s"] for r in post_proof) if post_proof else None)
                row[f"post_proof_{label}_expanded_median"] = (
                    distribution([r["post_proof_partial_expanded"] for r in post_proof])[0] if post_proof else None)
            for measure in MEASURES:
                cap = distribution([r[measure] for r in ranked])
                exact = distribution([right[measure] for _, right in comparisons])
                matched_base = distribution([left[measure] for left, _ in comparisons])
                paired_delta = distribution([right[measure] - left[measure] for left, right in comparisons
                                             if right[measure] is not None and left[measure] is not None])
                for suffix, values in (("all", cap), ("cocert", exact), ("cocert_current", matched_base),
                                       ("paired_delta", paired_delta)):
                    row.update({f"{measure}_{suffix}_{label}": value
                                for label, value in zip(("median", "p95", "max"), values)})
            lower = [right["online_elapsed_s"] - left["online_elapsed_s"] for left, right in paired
                     if left["delivery_status"] in EXACT and right["delivery_status"] == CAPPED
                     and right["online_elapsed_s"] is not None and left["online_elapsed_s"] is not None
                     and right["limit_reason"] and "wall_time" in right["limit_reason"]]
            row["wall_capped_pairs_n"] = len(lower)
            row["wall_capped_delta_lower_bound_median_s"] = median(lower) if lower else None
            operational = distribution([right["operational_elapsed_s"] - left["operational_elapsed_s"]
                                        for left, right in paired if right["operational_elapsed_s"] is not None
                                        and left["operational_elapsed_s"] is not None])
            for field, value in zip(("median", "p95", "max"), operational):
                row[f"operational_paired_delta_{field}_s"] = value
            summaries.append(row)
    return summaries


def short_correctness_table(rows, methods):
    result = []
    for method in methods:
        for depth_scope, subset in (
            ("≤2", [r for r in rows if r["effective_depth"] < 3]),
            ("3", [r for r in rows if r["effective_depth"] == 3]),
        ):
            cases = [r for r in subset if r["method"] == method]
            if not cases:
                continue
            counts = Counter(r["prefix_status"] for r in cases)
            proto = Counter(r["protocol_status"] for r in cases if r["k"] == 500)
            result.append([method, depth_scope, len(cases), counts[FULL], counts[SHORT],
                           counts[CAPPED], counts[UNSOUND], counts["NOT_RUN"] + counts["STOPPED_AFTER_UNSOUND"],
                           proto["COMPLETE"], proto["PARTIAL_PREFIX"], proto["INSUFFICIENT_PREFIX"]])
    return tabular(("方法", "深度", "计划检查点", "全长", "短域", "限额", "不健全", "未运行",
                    "协议完整", "协议有限前缀", "协议前缀不足"), result)


def attribution_table(summaries):
    arm_metric = dict(zip(ABLATIONS, (
        "terminal_duplicates", "bound_evaluations", "deferred_capability_rejects",
        "coarsened_envelopes", "post_proof_partial_expanded", "raw_asts_materialized",
    )))
    rows = []
    for record in summaries:
        method = record["method"]
        if method not in arm_metric or record["cohort"] not in ("high_cost", "sparse", "depth3", "depth_le_2"):
            continue
        stat = arm_metric[method]
        rows.append((record["cohort"], method, record["shared_exact_delivery_n"],
                     fmt(record["online_elapsed_s_paired_delta_median"]),
                     fmt(record["partial_nodes_expanded_paired_delta_median"]),
                     fmt(record["operational_paired_delta_median_s"]),
                     record["wall_capped_pairs_n"],
                     fmt(record["wall_capped_delta_lower_bound_median_s"]),
                     f"{stat} = {fmt(record[f'{stat}_all_median'])}"))
    return tabular(("集合", "消融", "共同精确交付 n", "配对耗时 Δ 秒", "配对展开 Δ",
                    "限额处罚后配对 Δ 秒", "墙钟截尾配对 n", "时差下界中位 秒", "该机制工作量中位"), rows)


def decision_for(attempts, summaries):
    counts = Counter(r["correctness"] for r in attempts)
    if counts[UNSOUND] or counts["STOPPED_AFTER_UNSOUND"] or counts["NOT_RUN"]:
        return "METHOD_EVALUATION_BLOCKED", "比较存在不健全记录或未完成的计划尝试。"
    if any(r.get("protocol_prefix_match") is not True for r in attempts):
        return "METHOD_EVALUATION_BLOCKED", "同一输入前缀的协议核对不完整。"
    summary = {(r["cohort"], r["method"]): r for r in summaries}
    focus = summary[("high_cost", GENERIC)]
    base = summary[("high_cost", CURRENT)]
    # Claim measured paired advantage only where enough shared exact results
    # exist to interpret the high-cost comparisons, even if other rows cap.
    median_gain = focus["online_elapsed_s_paired_delta_median"]
    if base["exact_delivery_n"] < base["planned_n"] or (
            focus["shared_exact_delivery_n"] < min(8, focus["planned_n"])
            and focus["wall_capped_pairs_n"] < max(1, math.ceil(focus["planned_n"] * .50))):
        return "METHOD_EVALUATION_BLOCKED", "高成本目标上当前方法覆盖或比较证据不足。"
    bound = summary[("high_cost", "GENERIC_BOUND_ONLY")]["partial_nodes_expanded_paired_delta_median"]
    env = summary[("high_cost", "WEAK_STATE_TIME_RESOURCE_ENVELOPE")]["partial_nodes_expanded_paired_delta_median"]
    advantage = (median_gain is not None and median_gain > 0) or (
        focus["wall_capped_pairs_n"] >= math.ceil(focus["planned_n"] * .50)
        and (focus["wall_capped_delta_lower_bound_median_s"] or 0) > 0)
    if not advantage:
        return "METHOD_WEAK_AGAINST_GENERIC", "高成本同域对照中没有看到明确的在线耗时优势。"
    if bound is None or env is None:
        return "METHOD_EVALUATION_BLOCKED", "在线对照显示差异，关键单因素比较的共同认证证据不足。"
    if bound <= 0 and env <= 0:
        return "METHOD_EVALUATION_BLOCKED", "在线对照显示差异，两个领域机制的独立工作量优势尚未得到验证。"
    return "METHOD_READY_FOR_FREEZE_REVIEW", "同域配对显示在线优势，且单因素测试支持至少一项领域抽象减少展开。"


def main():
    plan = read_json(HERE / "development_plan.json")
    for name, digest in plan["sources"].items():
        if hash_file(HERE / name) != digest:
            raise RuntimeError(f"Source drift after plan lock: {name}")
    attempts, rows = flatten(plan)
    for row in attempts:
        if row["correctness"] not in ("CONSISTENT_WITH_SEALED_REFERENCE", UNSOUND):
            continue
        if row["namespace"] != "GENSPACE-FAIL-01-PILOT":
            raise RuntimeError("A method attempt escaped the fixed development namespace")
        if row["method"] not in GRAPH_METHODS:
            audit = row.get("snapshot")
            if (not audit or audit["pass"] is not True or audit["blocked"]
                    or not audit["forbidden_call_counts"] or any(audit["forbidden_call_counts"].values())):
                raise RuntimeError("Missing or failed graph-independent access audit")
    cohorts = selections([r for r in rows if r["k"] == 500])
    summaries = summarize(cohorts)
    write_csv("per_query.csv", FIELDS, rows)
    write_csv("ablation_summary.csv", list(summaries[0]), [s for s in summaries if s["method"] in ABLATIONS])
    write_csv("comparison_summary.csv", list(summaries[0]), summaries)

    reduced = read_json(HERE / "reduced_correctness.json")
    bound_check = read_json(HERE / "generic_bound_checks.json")
    status, reason = decision_for(attempts, summaries)
    correct_n = sum(r["correctness"] == "CONSISTENT_WITH_SEALED_REFERENCE" for r in attempts)
    tested = sum(r.get("protocol_prefix_match") is True for r in attempts)
    exact_n = sum(r["prefix_status"] in EXACT for r in rows)
    match_text = (f"封存的 96 个原深度查询和 24 个 depth3 查询是共同参照。已检查 {correct_n}/{len(attempts)} 个方法×查询，"
                  f"共 {exact_n}/{len(rows)} 个检查点取得完整或短域证书。{tested} 个方法×查询的同输入前缀协议"
                  "重放逐字段一致，含独立复核双方效用和 Nash。协议需超出已知前缀时保留不完整状态。")
    methods = (CURRENT, GENERIC, *GRAPH_METHODS)
    write_report("PAPER_BASELINE_CORRECTNESS_REPORT.md", "# 开发集基线正确性",
                 match_text, short_correctness_table(rows, methods),
                 f"通用基线在 {reduced['pass_by_method'][GENERIC]} 个独立缩减域通过全域签名、顺序、"
                 "binary64 分数、原始与规范代表以及穷尽检查。额外下界证据记录在 "
                 "[generic_bound_checks.json](results/paper_method_dev/generic_bound_checks.json)。"
                 f"该证据状态为 {bound_check.get('status', '见原始记录')}。",
                 "Depth 3 的一般规模核对以封存的精确前缀和当前前沿证书为参照。完整 FLAT 和两类索引的 Depth 3 结果为 N/A。",
                 "首轮预检在 JSON 预算键类型上产生 11 条假差异。它们的前缀摘要已匹配。"
                 "统一运输键后，同一前缀重放的 11 条协议记录也逐字段相等。该预检不进入计时统计。"
                 " [传输核对](results/paper_method_dev/transport_checker_preflight/corrected_transport_check.json)")

    write_report("PAPER_ABLATION_CORRECTNESS.md", "# 六项消融正确性",
                 "全部消融保持冻结 DSL、能力定义、公开分数、规范键、并列顺序与原双边接受规则。",
                 "完整有限缩减域通过数如下。完整规模检查按认证、限额和不健全分别记账。",
                 tabular(("消融", "缩减域精确一致"), [(m, reduced["pass_by_method"].get(m, 0)) for m in ABLATIONS]),
                 short_correctness_table(rows, ABLATIONS),
                 "A5 的 K 证书在首次可得时保存，取消停止后的交付状态单独记录。A6 推迟规范化会改变早期可识别的等价关系，"
                 "测得的是在该表示下的边际影响。")

    measurements = []
    for row in summaries:
        get = lambda field: " / ".join(fmt(row.get(f"{field}_all_{x}")) for x in ("median", "p95", "max"))
        measurements.append((row["cohort"], row["method"], f"{row['exact_delivery_n']}/{row['planned_n']}",
                             get("online_elapsed_s"), get("partial_nodes_expanded"),
                             get("complete_assignments_examined"), get("peak_rss_mib")))
    write_report("PAPER_DEVELOPMENT_COMPARISON.md", "# PAPER-BASELINE-ABLATION-01 · 开发集比较",
                 f"**{status}**。{reason}", match_text,
                 "同一批既有查询按固定顺序交错深度和轮换方法，每一时刻只执行一个查询。"
                 "高成本集合在结果读取前按原深度冻结公开合格候选数 ≥100,000 定义。"
                 "下面的秒数包括限额前已做的工作。限额中的行不能代表完成耗时。",
                 tabular(("集合", "方法", "交付", "耗时 s median/p95/max", "展开 median/p95/max",
                          "完整赋值 median/p95/max", "采样峰值 MiB median/p95/max"), measurements),
                 "以下消融差值为消融减当前方法。共同认证配对与全队列处罚后配对分开解释。"
                 "处罚秒数为预设墙钟上限。墙钟截尾行的实做时间可作完成时长下界。"
                 "A5 的 post-proof 工作量包含限额前的额外搜索，未穷尽时仅为下界。",
                 attribution_table(summaries),
                 "逐条结果含分数调用、下界调用、前沿峰值、认证状态和双边结果。"
                 "候选赋值、语义状态、原始 witness AST 和索引记录访问是不同事件。"
                 "固定开发面板仅作描述性解读，不将重用查询的统计量外推为独立确认。",
                 "[逐查询 CSV](results/paper_method_dev/per_query.csv) · "
                 "[全部汇总](results/paper_method_dev/comparison_summary.csv) · "
                 "[消融汇总](results/paper_method_dev/ablation_summary.csv)")

    protected = read_json(ARCHIVE / "paper_method_review" / "protected_inputs_sha256.json")
    protected_equal = all(hash_file(ROOT / path) == digest for path, digest in protected["files"].items())
    if not protected_equal or (ROOT / "FROZEN_CONFIG.yaml").exists():
        raise RuntimeError("Protected historical data or authorization scope changed")
    evidence = {
        "status": status, "reason": reason, "planned_attempts": len(attempts),
        "observed_attempts": sum(r["correctness"] != "NOT_RUN" for r in attempts),
        "protocol_match": tested, "exact_checkpoints": exact_n, "planned_checkpoints": len(rows),
        "protected_files_unchanged": len(protected["files"]),
        "development_plan_sha256": hash_file(HERE / "development_plan.json"),
        "shared_immutable_kernel_sources": read_json(
            ARCHIVE / "depth3" / "regression" / "online_manifest.json")["sources"],
        "candidate_method_sources": plan["sources"],
        "python": plan["python"], "numpy": plan["numpy"],
    }
    (HERE / "development_decision.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8")
    write_report("PAPER_METHOD_FREEZE_RECOMMENDATION.md", "# 论文方法冻结前审核",
                 f"**{status}**。{reason}",
                 f"本轮仅使用已封存开发查询。历史保护清单的 {len(protected['files'])} 个文件逐字节哈希一致。",
                 "正式样本、版本和效应门槛留待独立确认前审核。原 9,600 实例计划与 Gate A–E "
                 "属于固定空间研究，继续保留原目的。",
                 "本分类是开发集冻结审核建议。判断考虑高成本共同认证差值、可解释的墙钟截尾下界和领域机制工作计数。"
                 "已保存方法与运行计划哈希，供审核时锁定。这些规则与样本不用于确认推断。",
                 "[开发决策记录](results/paper_method_dev/development_decision.json) · "
                 "[方法确认草稿](METHOD_CONFIRMATION_PREREGISTRATION_DRAFT.md)")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
