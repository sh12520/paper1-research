"""Exact receive-side prework for the frozen OPV2V MAX-fusion receiver."""

from contextlib import nullcontext
from dataclasses import dataclass
from struct import Struct
from unittest.mock import patch

import numpy as np
import torch
import torch.nn.functional as F

from opv2v_r23_prefilter import PrefilterTrace, postprocess_prefilter


HEADER = Struct('<IBBB9s')
HEADS = ('cls_preds', 'reg_preds', 'dir_preds')


def timed(clock, stage, function, *args, event=True):
    if clock is None:
        return function(*args)
    return clock.call(stage, function, *args, event=event)


@dataclass(frozen=True)
class PreparedPacket:
    sender: int
    levels: tuple
    wire_bytes: int
    h2d_bytes: int


def parse_packet(frame, packet):
    """Parse the three wire index/value sets using only geometry and this payload."""
    raw = packet.payload
    if len(raw) < HEADER.size or len(frame.pyramid) != 3:
        raise ValueError('Expected a complete feature packet and three frozen pyramid levels')
    _, sender, receiver_flags, _, sizes = HEADER.unpack_from(raw)
    if not 1 <= sender < frame.count or receiver_flags & 0x1f:
        raise ValueError('Feature payload addresses the wrong sender or receiver')
    offset, levels = HEADER.size, []
    for level, pyramid in enumerate(frame.pyramid):
        channels, height, width = pyramid.shape[1:]
        count = int.from_bytes(sizes[3 * level:3 * (level + 1)], 'little')
        index_end = offset + count * 2
        value_end = index_end + count * channels * 4
        if value_end > len(raw):
            raise ValueError('Feature packet ends inside a declared pyramid level')
        index = np.frombuffer(raw, dtype='<u2', count=count, offset=offset).astype(np.int64)
        if count and (index[-1] >= height * width or np.any(index[1:] <= index[:-1])):
            raise ValueError('Feature packet index is duplicated, out of order, or outside the grid')
        values = np.frombuffer(raw, dtype='<f4', count=count * channels, offset=index_end).copy()
        levels.append((index, values.reshape(count, channels).T))
        offset = value_end
    if offset != len(raw):
        raise ValueError('Trailing bytes in complete pyramid packet')
    return sender, tuple(levels)


def prepare_packet(frame, packet, clock=None):
    """Prepare immutable packet tensors on the current device stream."""
    sender, arrays = timed(clock, 'packet_cpu_parse', parse_packet, frame, packet, event=False)

    def upload():
        return tuple((torch.as_tensor(index, device=frame.device), torch.as_tensor(values, device=frame.device))
                     for index, values in arrays)

    levels = timed(clock, 'packet_h2d', upload)
    copied = sum(index.nbytes + values.nbytes for index, values in arrays) if frame.device.type == 'cuda' else 0
    return PreparedPacket(sender, levels, len(packet.payload), copied)


def validate_packet_union(frame, packets):
    """Prove arbitrary arrival scattering preserves the independent packet vectors."""
    from run_opv2v_r22_fusion import adopted_support, packet_values

    widths = tuple(level.shape[1] for level in frame.pyramid)
    support = {key: packet_values(packet.payload, key[0], widths) for key, packet in packets.items()}
    fine, index_value_bytes, digest = adopted_support(tuple(packets), support)
    return {'unique_fine_cells': fine, 'unique_feature_index_and_vector_bytes': index_value_bytes,
            'feature_union_sha256': digest, 'wire_bytes': sum(len(packet.payload) for packet in packets.values()),
            'packets': len(packets), 'overlapping_vectors_byte_equal': True}


@dataclass(frozen=True)
class FrameInput:
    masks: tuple
    raw_levels: tuple
    senders: tuple
    packets: tuple

    def record_stream(self, stream):
        """Protect snapshot storage when its owner drops it before a CUDA reader completes."""
        for tensor in (*self.masks, *(value for levels in self.raw_levels for value in levels)):
            tensor.record_stream(stream)


class ReceiverCache:
    """Store unweighted sender vectors and fine support, one write per received packet."""

    def __init__(self, frame):
        self.frame = frame
        self.masks = {}
        self.raw_levels = {}
        self.active_senders = set()
        self.received = set()
        self.order = []

    def ingest(self, key, prepared, clock=None):
        """Call from the ingress stream after validation of repeated wire vectors."""
        if key in self.received or prepared.sender != key[0]:
            raise ValueError('Repeated or misaddressed packet in the receiver')
        sender = prepared.sender
        if sender not in self.raw_levels:
            def allocate():
                return torch.zeros_like(self.frame.empty), tuple(torch.zeros_like(pyramid[sender])
                                                                  for pyramid in self.frame.pyramid)

            self.masks[sender], self.raw_levels[sender] = timed(clock, 'packet_cache_allocate', allocate)

        def scatter():
            fine_index = prepared.levels[0][0]
            self.masks[sender].flatten()[fine_index] = 1
            for grid, (index, values) in zip(self.raw_levels[sender], prepared.levels, strict=True):
                grid.reshape(grid.shape[0], -1)[:, index] = values

        timed(clock, 'packet_scatter_fine_union', scatter)
        if prepared.levels[0][0].numel():
            self.active_senders.add(sender)
        self.received.add(key)
        self.order.append(key)

    def snapshot(self, copy=True):
        """Publish a prefix on the ingress stream. Borrow only when writes have finished."""
        senders = tuple(sorted(self.active_senders))
        masks = tuple(self.masks[sender] for sender in senders)
        raw = tuple(self.raw_levels[sender] for sender in senders)
        if copy:
            masks = tuple(mask.clone() for mask in masks)
            raw = tuple(tuple(value.clone() for value in levels) for levels in raw)
        return FrameInput(masks, raw, senders, tuple(self.order))


def reference_input(frame, packets, chosen, clock=None):
    """Run the original replay's two wire decode passes in their original ordering."""
    def build_masks():
        masks, grouped = list(frame.zero_masks), {}
        for sender, phase in sorted(chosen, key=lambda key: (key[0], key[1] != 'first')):
            packet = packets[sender, phase]
            masks[sender - 1] = masks[sender - 1].maximum(packet.decode_mask())
            grouped.setdefault(sender, []).append(packet)
        return masks, grouped

    masks, grouped = timed(clock, 'reference_wire_masks', build_masks)

    def decode_values():
        senders = tuple(agent for agent, mask in enumerate(masks, 1) if bool(mask.count_nonzero()))
        decoded = []
        for sender in senders:
            levels = tuple(torch.zeros_like(pyramid[sender]) for pyramid in frame.pyramid)
            for packet in grouped.get(sender, ()):
                packet.decode_into(levels)
            decoded.append(levels)
        return FrameInput(tuple(masks[sender - 1] for sender in senders), tuple(decoded), senders, tuple(chosen))

    return timed(clock, 'reference_wire_values', decode_values)


def receiver_from_cache(frame, snapshot, clock=None, capture=None, prefilter_trace=None):
    """Run each global dependency on the current full mask union and raw vectors."""
    from opencood.models.sub_modules.torch_transformation_utils import warp_affine_simple

    def fuse():
        transform = frame.affine[0, 0, [0, *snapshot.senders]]
        fused = []
        for level, pyramid in enumerate(frame.pyramid):
            width = pyramid.shape[-2:]

            def weights():
                return tuple(F.interpolate(mask, size=width, mode='bilinear', align_corners=True)[0]
                             for mask in snapshot.masks)

            coefficients = timed(clock, 'fusion_mask_weights', weights)

            def weight_features():
                return tuple(levels[level] * weight for levels, weight in zip(snapshot.raw_levels, coefficients,
                                                                             strict=True))

            weighted = timed(clock, 'fusion_weight_features', weight_features)
            aligned = timed(clock, 'fusion_warp_pose', warp_affine_simple, torch.stack((pyramid[0], *weighted)),
                            transform, width)
            to_head = timed(clock, 'fusion_max_levels', frame.fusion.fuse_modules[level], aligned)[None]
            fused.append(to_head)
            if capture is not None:
                for sender, weight, feature in zip(snapshot.senders, coefficients, weighted, strict=True):
                    capture[f'weight/{sender}/{level}'] = weight
                    capture[f'weighted/{sender}/{level}'] = feature
                capture[f'aligned/{level}'] = aligned
                capture[f'fused/{level}'] = to_head
        return fused

    def detect(fused):
        features = timed(clock, 'pyramid_decode', frame.fusion.decode_multiscale_feature, fused)
        if frame.model.shrink_flag:
            features = timed(clock, 'pyramid_shrink', frame.model.shrink_conv, features)
        if capture is not None:
            capture['head_input'] = features

        def heads_forward():
            return {'cls_preds': frame.model.cls_head(features), 'reg_preds': frame.model.reg_head(features),
                    'dir_preds': frame.model.dir_head(features)}

        return timed(clock, 'detection_heads', heads_forward)

    if capture is not None:
        capture['packet_ids'] = tuple(sorted(snapshot.packets))
        capture['active_senders'] = snapshot.senders
        capture['implicit_vehicle_class'] = 0
        for sender, mask, levels in zip(snapshot.senders, snapshot.masks, snapshot.raw_levels, strict=True):
            capture[f'fine_mask/{sender}'] = mask
            capture.update({f'raw/{sender}/{level}': vector for level, vector in enumerate(levels)})
    if snapshot.senders:
        fused = timed(clock, 'fusion', fuse)
        heads = timed(clock, 'detection', detect, fused)
    else:
        heads = timed(clock, 'detection', frame.local, 0)
    if capture is not None:
        capture.update({f'head/{name}': heads[name] for name in HEADS})
    host_heads = timed(clock, 'heads_to_host', lambda: {name: heads[name].cpu() for name in HEADS})
    return postprocess(frame, host_heads, clock, capture, prefilter_trace)


def postprocess(frame, heads, clock=None, capture=None, trace=None):
    context = nullcontext()
    if capture is not None:
        from opencood.utils import box_utils

        original_nms = box_utils.nms_rotated
        trace = trace or PrefilterTrace()
        capture['nms_keep_indices'] = None

        def collect_kept(*args, **kwargs):
            kept = original_nms(*args, **kwargs)
            capture['nms_keep_indices'] = tuple(kept.tolist())
            return kept

        context = patch.object(box_utils, 'nms_rotated', collect_kept)

    with context:
        boxes, scores = timed(clock, 'cpu_postprocess', postprocess_prefilter,
                              frame.dataset.post_processor, frame.batch, {'ego': heads}, trace, event=False)
    if capture is not None:
        capture['candidate_indices'] = tuple(trace.candidate_indices)
        capture['boxes'] = boxes
        capture['scores'] = scores
    return boxes, scores


def receiver_reference(frame, packets, chosen, clock=None, capture=None, prefilter_trace=None):
    """Collect all raw messages after the last arrival, then use the same receiver tail."""
    snapshot = reference_input(frame, packets, chosen, clock)
    return receiver_from_cache(frame, snapshot, clock, capture, prefilter_trace)


def compare_captures(reference, candidate):
    """Compare traced intermediates by dtype/shape and exact bytes on their own devices."""
    details = {}
    for stage in sorted(reference.keys() | candidate.keys()):
        first, second = reference.get(stage), candidate.get(stage)
        if torch.is_tensor(first) and torch.is_tensor(second):
            compatible = first.shape == second.shape and first.dtype == second.dtype and first.device == second.device
            exact = compatible and torch.equal(first.contiguous().view(torch.uint8), second.contiguous().view(torch.uint8))
            row = {'exact': bool(exact), 'shape': list(first.shape), 'dtype': str(first.dtype), 'device': str(first.device),
                   'max_abs_error': 0.0 if exact else None}
            if compatible and not exact and first.numel():
                error = float((first.to(torch.float64) - second.to(torch.float64)).abs().amax())
                row['max_abs_error'] = error if np.isfinite(error) else None
        else:
            exact = (not torch.is_tensor(first) and not torch.is_tensor(second) and stage in reference and stage in candidate
                     and first == second)
            row = {'exact': bool(exact)}
            if stage in {'packet_ids', 'active_senders', 'implicit_vehicle_class'}:
                row['value'] = first
            if stage in {'candidate_indices', 'nms_keep_indices'}:
                row['count'] = len(first) if first is not None else None
        details[stage] = row
    return bool(details) and all(row['exact'] for row in details.values()), details


def cpu_equivalence():
    """Use archived real packet bytes and frozen model weights for the CPU gate."""
    import random
    from pathlib import Path
    from time import perf_counter_ns

    from run_opv2v_formal import DATA, ROOT, SEED, WEIGHT, WEIGHT_SHA, atomic, exclusive, import_model, native_panel, sha256
    from run_opv2v_r23 import frozen_panel, load, messages_for, run_receiver
    from run_opv2v_r2_runtime import Stopwatch

    output = ROOT / 'results/opv2v-r25'
    receipt = output / 'cpu-equivalence.json'
    proof, archives = frozen_panel(True)
    archive, = archives
    metadata = {'core_sha256': sha256(Path(__file__)), 'frozen_smoke_proof_sha256': sha256(proof),
                'archived_frame_sha256': archive.sha, 'model_weights_sha256': WEIGHT_SHA, 'frame_key': archive.key,
                'model_path': 'frozen BlindMap TMC epoch 37', 'device': 'cpu', 'seed': SEED, 'threads': 2}
    with exclusive(output):
        if receipt.is_file():
            previous = load(receipt)
            if any(previous[key] != value for key, value in metadata.items()):
                raise ValueError('Existing R2.5 CPU gate belongs to another source version')
            return previous
        if sha256(WEIGHT) != WEIGHT_SHA:
            raise ValueError('Frozen checkpoint bytes changed')
        model, dataset, device, torch_backend = import_model(None, DATA / 'test', 2)
        from replay_opv2v import FrameReplay

        torch_backend.use_deterministic_algorithms(True, warn_only=True)
        np.random.seed(SEED)
        random.seed(SEED)
        with torch_backend.inference_mode():
            index = native_panel(dataset)[archive.key]
            frame = FrameReplay(model, dataset, dataset.collate_batch_test([dataset[index]]), device, archive.ordinal)
            packets = messages_for(frame, archive)['fragment']
            union = validate_packet_union(frame, packets)
            arrivals = archive.record['sizes']['16384']['network_transmissions']
            keys = tuple((row['sender'], row['kind']) for row in sorted(arrivals, key=lambda row: row['arrival_ms']))
            cache = ReceiverCache(frame)
            partial_count = max(1, len(keys) // 2)
            clock = Stopwatch(torch_backend, device)
            clock.start_ns = perf_counter_ns()
            for i, key in enumerate(keys, 1):
                cache.ingest(key, prepare_packet(frame, packets[key], clock), clock)
                if i == partial_count:
                    early_snapshot = cache.snapshot(copy=True)

            states = {}
            for name, snapshot, chosen in (('immutable_partial_after_later_arrivals', early_snapshot, keys[:partial_count]),
                                            ('complete', cache.snapshot(copy=False), keys)):
                reference, streamed = {}, {}
                expected = receiver_reference(frame, packets, chosen, capture=reference)
                actual = receiver_from_cache(frame, snapshot, capture=streamed)
                native, _, _ = run_receiver(frame, packets, chosen, postprocess_prefilter, None, None)
                same, stages = compare_captures(reference, streamed)
                direct, heads = compare_captures(dict(zip(('boxes', 'scores'), native, strict=True)),
                                                 dict(zip(('boxes', 'scores'), actual, strict=True)))
                direct_to_reference, _ = compare_captures(dict(zip(('boxes', 'scores'), native, strict=True)),
                                                           dict(zip(('boxes', 'scores'), expected, strict=True)))
                states[name] = {'packets': len(chosen), 'all_stage_checks_exact': same,
                                'matches_unchanged_r23_receiver': direct and direct_to_reference,
                                'stage_checks': stages, 'unchanged_r23_output': heads}
        passed = all(row['all_stage_checks_exact'] and row['matches_unchanged_r23_receiver'] for row in states.values())
        result = {**metadata, 'status': 'verified' if passed else 'mismatch', 'states': states,
                  'wire_union': union, 'packet_warmup_stage_intervals_cpu': clock.measures(),
                  'archived_frozen_frame_excluded_from_screen': True}
        atomic(receipt, result)
        return result


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu-equivalence', action='store_true', required=True)
    parser.parse_args()
    raise SystemExit(0 if cpu_equivalence()['status'] == 'verified' else 2)
