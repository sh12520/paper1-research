#!/usr/bin/env python3
"""Isolated sparse anchor decoding for the frozen single-ego OPV2V detector."""

import argparse
from collections import defaultdict
from contextlib import ExitStack
import os
import sys
from time import perf_counter_ns
from unittest.mock import patch


HEAD_NAMES = {"cls_preds", "reg_preds", "dir_preds"}


class PrefilterTrace:
    """Collect CPU wall-clock intervals and ordered anchor identities in a traced trial."""

    def __init__(self):
        self.anchor_count = 0
        self.decoded_count = 0
        self.times_ms = defaultdict(list)
        self._mask = None
        self._indices = None

    @property
    def candidate_indices(self):
        if self._indices is not None:
            return self._indices.tolist()
        if self._mask is not None:
            return self._mask.flatten().nonzero().flatten().tolist()
        return []

    def call(self, name, function, *args, **kwargs):
        start = perf_counter_ns()
        result = function(*args, **kwargs)
        self.times_ms[name].append((perf_counter_ns() - start) / 1e6)
        return result

    def as_dict(self):
        return {"anchor_count": self.anchor_count, "actual_decoded_count": self.decoded_count,
                "candidate_indices": self.candidate_indices, "stage_wall_ms": dict(self.times_ms)}


def direct(_stage, function, *args, **kwargs):
    return function(*args, **kwargs)


def frozen_inputs(data_dict, output_dict):
    """Scope the adapter to the frozen one-class, single-ego CPU postprocessor."""
    if set(output_dict) != {"ego"} or set(output_dict["ego"]) != HEAD_NAMES:
        raise ValueError("R2.3 requires the frozen ego-only classification, regression and direction heads")
    heads = output_dict["ego"]
    cls, reg, direction = (heads[name] for name in ("cls_preds", "reg_preds", "dir_preds"))
    ego = data_dict["ego"]
    anchors = ego["anchor_box"]
    if cls.ndim != 4 or cls.shape[0] != 1:
        raise ValueError("R2.3 requires batch-size-one anchor-based outputs")
    _, priors, height, width = cls.shape
    if (reg.shape != (1, 7 * priors, height, width)
            or direction.ndim != 4 or direction.shape[0] != 1 or direction.shape[-2:] != (height, width)
            or anchors.shape != (height, width, priors, 7) or cls.device.type != "cpu"
            or cls.device != reg.device or cls.device != direction.device or cls.device != anchors.device):
        raise ValueError("R2.3 requires frozen CPU heads and anchor geometry with matching flattened order")
    return ego, cls, reg, direction


def probabilities(cls):
    import torch.nn.functional as F

    return F.sigmoid(cls.permute(0, 2, 3, 1)).reshape(1, -1)


def surviving_indices(prob, threshold):
    import torch

    return torch.gt(prob, threshold).flatten().nonzero().flatten()


def gather_geometry(reg, anchors, indices, priors):
    # Native flattening is row, column, then anchor orientation. Index the
    # original layout directly so we never transpose/copy the dense reg map.
    width = reg.shape[-1]
    positions = indices // priors
    deltas = reg[0].unflatten(0, (priors, 7))[indices % priors, :, positions // width, positions % width]
    # Reuse the native pointwise decoder and its dtype/operation order. The
    # geometry still represents the original anchors after this sparse reshape.
    return deltas.T.reshape(1, 7, -1, 1), anchors.view(-1, 7).index_select(0, indices)


def selected_direction(boxes, direction, indices, params):
    import numpy as np
    import torch
    from opencood.utils.common_utils import limit_period

    offset = params["dir_args"]["dir_offset"]
    bins = params["dir_args"]["num_bins"]
    # Keep the native tie-breaking and floating operations for direction logits.
    logits = direction.permute(0, 2, 3, 1).contiguous().reshape(-1, bins).index_select(0, indices)
    labels = torch.max(logits, dim=-1)[1]
    period = 2 * np.pi / bins
    yaw = limit_period(boxes[..., 6] - offset, 0, period)
    boxes[..., 6] = yaw + offset + period * labels.to(logits.dtype)
    boxes[..., 6] = limit_period(boxes[..., 6], 0.5, 2 * np.pi)


def project_and_filter(boxes, scores, transformation, params):
    import torch
    from opencood.utils import box_utils

    corners = box_utils.boxes_to_corners_3d(boxes, order=params["order"])
    projected = box_utils.project_box3d(corners, transformation)
    standup = box_utils.corner_to_standup_box_torch(projected)
    # Reuse native stack and score assembly to preserve score dtype promotion.
    scores = torch.vstack([torch.cat((standup, scores.unsqueeze(1)), dim=1)])[:, -1]
    projected = torch.vstack([projected])
    keep = torch.logical_and(box_utils.remove_large_pred_bbx(projected), box_utils.remove_bbx_abnormal_z(projected))
    return projected[keep], scores[keep]


def filter_range(boxes, scores, params):
    import torch
    from opencood.utils import box_utils

    filtered, mask = box_utils.mask_boxes_outside_range_numpy(boxes.cpu().numpy(), params["gt_range"],
                                                             order=None, return_mask=True)
    filtered = torch.from_numpy(filtered).to(device=boxes.device)
    scores = scores[mask]
    assert scores.shape[0] == filtered.shape[0]
    return filtered, scores


def postprocess_prefilter(postprocessor, data_dict, output_dict, trace=None):
    """Move only the native strict score filter ahead of pointwise anchor decoding."""
    if trace is None:
        return _postprocess_prefilter(postprocessor, data_dict, output_dict, None)
    return trace.call("postprocess_total", _postprocess_prefilter, postprocessor, data_dict, output_dict, trace)


def _postprocess_prefilter(postprocessor, data_dict, output_dict, trace):
    from opencood.utils import box_utils

    timed = direct if trace is None else trace.call
    ego, cls, reg, direction = frozen_inputs(data_dict, output_dict)
    params = postprocessor.params
    prob = timed("classification", probabilities, cls)
    indices = timed("candidate_filter", surviving_indices, prob, params["target_args"]["score_threshold"])
    if trace is not None:
        trace.anchor_count = prob.numel()
        trace.decoded_count = len(indices)
        trace._indices = indices
    if not len(indices):
        return None, None

    deltas, anchors = timed("candidate_regression_gather", gather_geometry, reg, ego["anchor_box"], indices, cls.shape[1])
    boxes = timed("anchor_decode", postprocessor.delta_to_boxes3d, deltas, anchors)[0]
    scores = timed("candidate_filter", prob[0].index_select, 0, indices)
    timed("direction", selected_direction, boxes, direction, indices, params)
    boxes, scores = timed("geometry_filter", project_and_filter, boxes, scores, ego["transformation_matrix"], params)
    keep = timed("rotated_nms", box_utils.nms_rotated, boxes, scores, params["nms_thresh"])
    return timed("final_range_filter", filter_range, boxes[keep], scores[keep], params)


def trace_native_postprocess(postprocessor, data_dict, output_dict, trace=None):
    """Measure the unchanged native control path using scoped helper hooks."""
    if trace is None:
        return postprocessor.post_process(data_dict, output_dict)

    import torch
    import torch.nn.functional as F
    from opencood.utils import box_utils

    ego, _, _, _ = frozen_inputs(data_dict, output_dict)
    trace.anchor_count = ego["anchor_box"].numel() // 7
    with ExitStack() as stack:
        def watch(owner, field, stage, after=None):
            native = getattr(owner, field)

            def measured(*args, **kwargs):
                value = trace.call(stage, native, *args, **kwargs)
                if after is not None:
                    after(value)
                return value

            stack.enter_context(patch.object(owner, field, measured))

        def capture_mask(mask):
            if mask.shape == (1, trace.anchor_count):
                trace._mask = mask

        def capture_decode(decoded):
            trace.decoded_count = decoded.shape[1]

        watch(F, "sigmoid", "classification")
        watch(torch, "gt", "candidate_filter", capture_mask)
        watch(torch, "masked_select", "candidate_filter")
        watch(postprocessor, "delta_to_boxes3d", "anchor_decode", capture_decode)
        watch(box_utils, "boxes_to_corners_3d", "geometry_filter")
        watch(box_utils, "project_box3d", "geometry_filter")
        watch(box_utils, "corner_to_standup_box_torch", "geometry_filter")
        watch(box_utils, "remove_large_pred_bbx", "geometry_filter")
        watch(box_utils, "remove_bbx_abnormal_z", "geometry_filter")
        watch(box_utils, "nms_rotated", "rotated_nms")
        watch(box_utils, "mask_boxes_outside_range_numpy", "final_range_filter")
        return trace.call("postprocess_total", postprocessor.post_process, data_dict, output_dict)


def tensor_difference(reference, candidate):
    """Distinguish exact value agreement, byte agreement and numerical error."""
    import torch

    if reference is None or candidate is None:
        same = reference is candidate
        return {"same_shape_and_dtype": same, "values_equal": same, "bytes_equal": same,
                "max_abs_error": 0.0 if same else None}
    comparable = reference.shape == candidate.shape and reference.dtype == candidate.dtype
    if not comparable:
        return {"same_shape_and_dtype": False, "values_equal": False, "bytes_equal": False, "max_abs_error": None}
    first = reference.detach().cpu().contiguous()
    second = candidate.detach().cpu().contiguous()
    values_equal = torch.equal(first, second)
    max_abs_error = 0.0
    if first.numel():
        largest = (first.to(torch.float64) - second.to(torch.float64)).abs().amax()
        max_abs_error = float(largest) if torch.isfinite(largest) else None
    return {"same_shape_and_dtype": True, "values_equal": values_equal,
            "bytes_equal": torch.equal(first.view(torch.uint8), second.view(torch.uint8)), "max_abs_error": max_abs_error}


def compare_postprocess(reference, candidate):
    return {name: tensor_difference(first, second)
            for name, first, second in zip(("boxes", "scores"), reference, candidate, strict=True)}


def cpu_smoke(threads):
    from pathlib import Path

    from run_opv2v_feedback_control import check, read
    from run_opv2v_formal import ROOT, SOURCE, REVISION, atomic, exclusive, sha256
    from run_opv2v_r22_postprocess import NATIVE_POSTPROCESS_FILES, checked_capture

    capture = ROOT / "results/opv2v-r22-postprocess/capture"
    output = ROOT / "results/opv2v-r23/cpu-smoke"
    capture_marker = capture / "completion.json"
    marker, run = read(capture_marker), read(capture / "run.json")
    persisted = output / "completion.json"
    failed = output / "failure.json"
    metadata = {"core_sha256": sha256(Path(__file__)), "capture_completion_sha256": sha256(capture_marker),
                "capture_run_sha256": sha256(capture / "run.json"), "native_revision": REVISION,
                "threads": threads, "native_postprocess_files": {name: sha256(SOURCE / name) for name in NATIVE_POSTPROCESS_FILES}}
    check(marker["status"] == "complete" and marker["run_sha256"] == metadata["capture_run_sha256"]
          and len(marker["frames"]) == len(run["sample"]) == 2
          and metadata["native_postprocess_files"] == run["native_postprocess_files"],
          "R2.3 requires the unmodified native code and four sealed GPU head states")
    with exclusive(output):
        if persisted.is_file():
            row = read(persisted)
            check(all(row[key] == value for key, value in metadata.items()) and row["status"] == "complete"
                  and row["all_exact"] and row["states_verified"] == 4, "Existing R2.3 CPU smoke receipt changed")
            print("R2.3 CPU smoke reused four verified states", flush=True)
            return 0
        check(not failed.exists(), "A previous R2.3 CPU smoke mismatch has been retained")
        sys.path.insert(0, str(SOURCE))
        import torch
        from opencood.data_utils.post_processor.voxel_postprocessor import VoxelPostprocessor

        torch.set_num_threads(threads)
        states = []
        with torch.inference_mode():
            for item, sample in zip(marker["frames"], run["sample"], strict=True):
                manifest = ROOT / item["path"]
                check(sha256(manifest) == item["sha256"], "Archived GPU head manifest changed")
                source = checked_capture(manifest, sample, marker["run_sha256"])
                post = VoxelPostprocessor(source["postprocessor_params"], train=False)
                for variant, state in source["states"].items():
                    saved = torch.load(ROOT / state["inputs_path"], map_location="cpu", weights_only=True)
                    data, heads = {"ego": saved["native_inputs"]}, {"ego": saved["heads"]}
                    ordinary, sparse = PrefilterTrace(), PrefilterTrace()
                    reference = trace_native_postprocess(post, data, heads, ordinary)
                    candidate = postprocess_prefilter(post, data, heads, sparse)
                    original = {name: [] if value is None else value.tolist() for name, value in
                                zip(("boxes_8x3", "scores"), reference, strict=True)}
                    same_archive = original == state["detect"]
                    same_candidates = ordinary.candidate_indices == sparse.candidate_indices
                    ego, cls, reg, _ = frozen_inputs(data, heads)
                    indices = torch.as_tensor(sparse.candidate_indices, dtype=torch.int64)
                    deltas, anchors = gather_geometry(reg, ego["anchor_box"], indices, cls.shape[1])
                    before_native = post.delta_to_boxes3d(reg, ego["anchor_box"])[0].index_select(0, indices)
                    before_sparse = post.delta_to_boxes3d(deltas, anchors)[0]
                    differences = {**compare_postprocess(reference, candidate),
                                   "decoded_geometry_before_direction": tensor_difference(before_native, before_sparse)}
                    good = (same_archive and same_candidates and ordinary.decoded_count == 131072
                            and sparse.decoded_count == len(sparse.candidate_indices)
                            and all(row["bytes_equal"] and row["values_equal"] for row in differences.values()))
                    states.append({"frame_key": source["frame_key"], "variant": variant, "input_sha256": state["inputs_sha256"],
                                   "archived_detection_sha256": state["archived_detection_sha256"],
                                   "same_archived_native_output": same_archive, "same_ordered_candidates": same_candidates,
                                   "score_threshold": post.params["target_args"]["score_threshold"], "nms_threshold": post.params["nms_thresh"],
                                   "native_anchor_count": ordinary.decoded_count, "optimized_anchor_count": sparse.decoded_count,
                                   "native_candidate_indices": ordinary.candidate_indices,
                                   "optimized_candidate_indices": sparse.candidate_indices,
                                   "diff": differences, "exact": good})
                    print(f"{source['panel_index']:04d}-{variant}: {ordinary.decoded_count} → {sparse.decoded_count}, exact={good}", flush=True)
        all_exact = len(states) == 4 and all(row["exact"] for row in states)
        result = {**metadata, "status": "complete" if all_exact else "failed_exactness", "all_exact": all_exact,
                  "states_verified": len(states), "states": states, "torch": torch.__version__,
                  "scope": "CPU postprocess comparison on all four archived genuine R2.2 GPU head states, no speed claim from smoke",
                  "class_semantics": "single implicit vehicle class; direction-bin argmax only changes heading; no class IDs emitted",
                  "native_operation_order": ["classification convolution logits, box regression and direction heads",
                                             "permute classification logits then sigmoid and flatten",
                                             "decode every anchor delta independently using its own anchor",
                                             "retain scores strictly greater than the frozen score threshold in flattened anchor order",
                                             "choose direction bin and normalize heading for retained anchors",
                                             "convert boxes to corners and transform into ego coordinates",
                                             "filter oversized and abnormal-height boxes",
                                             "native rotated NMS: descending score argsort with existing 1000 cap, then IoU suppression",
                                             "remove boxes outside evaluation range and apply the same mask to scores"]}
        atomic(persisted if all_exact else failed, result)
        return 0 if all_exact else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", required=True)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    if args.threads <= 0:
        parser.error("--threads must be positive")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    return cpu_smoke(args.threads)


if __name__ == "__main__":
    raise SystemExit(main())
