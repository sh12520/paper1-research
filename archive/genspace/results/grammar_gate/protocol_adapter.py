"""Bridge a graph-free signature stream to the unchanged V1 protocol.

Only the current batch (at most sixteen signatures) is presented to the
existing packed PublicVerifier. Signature bytes replace graph IDs as stable
keys for the existing PrivateAgent and negotiate functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from types import SimpleNamespace

import numpy as np

from src.compact_semantics import CompactEncoder
from src.enumeration import syntax_key
from src.fast_runner import _decode_witness
from src.instances import demand, registry_from_public
from src.models import Static
from src.state_machine import verify_instance
from private_protocol import Evidence, PrivateAgent, PublicVerifier, negotiate
from runtime import BUDGETS, CHUNK, ROUND_LIMIT

import json


@dataclass(frozen=True)
class _PublicCandidate:
    key: bytes
    witness: str


def _public_cost_basis(public, roles):
    registry = registry_from_public(public)
    base_demand = np.array([
        [tuple(demand(public, profile, level, 0, 'still')[r] for r in ('RAN','FH','EDGE'))
         for level in ('none','edge')]
        for profile in public.b2_profiles
    ], dtype=np.float64)
    resources = np.empty((1 << len(roles), 3), dtype=np.float64)
    execution = np.empty(1 << len(roles), dtype=np.float64)
    for mask in range(len(execution)):
        selected = [registry[role] for i, role in enumerate(roles) if mask & (1 << i)]
        resources[mask] = [sum(c.resource_cost.get(r, 0.) for c in selected)
                           for r in ('RAN','FH','EDGE')]
        execution[mask] = sum(c.execution_cost for c in selected)
    return SimpleNamespace(base_demand=base_demand, role_costs=resources, execution_costs=execution)


class _BatchView:
    """Local verifier indices are reused; they never become protocol keys."""

    def __init__(self, depth):
        self.depth = depth
        self.eligible = np.empty(0, dtype=bool)
        self.witnesses = ()

    def mask(self, depth):
        if depth != self.depth:
            raise ValueError('mixed composition depth in packed verifier batch')
        return self.eligible

    def witness(self, local_id, depth):
        if not self.mask(depth)[local_id]:
            raise ValueError('no witness for local verifier row')
        return self.witnesses[local_id]


class _BatchVerifier:
    def __init__(self, public, depth, limit):
        self.depth = depth
        self.encoder = CompactEncoder(public)
        if (len(self.encoder.roles) != 12 or public.horizon != 3 or
                public.states != ('still','moving') or len(public.b2_profiles) != 27):
            raise ValueError('unsupported benchmark layout in packed verifier adapter')
        self.library = _public_cost_basis(public, self.encoder.roles)
        self.variant = _BatchView(depth)
        self.native = PublicVerifier(public, self.variant, depth, limit, self.library)

    def _bind_batch(self, candidates):
        if not 0 < len(candidates) <= CHUNK:
            raise ValueError('invalid verifier batch length')
        if any(type(c.key) is not bytes or len(c.key) != 49 or c.key[0] != 1 or
               not isinstance(c.witness, str) for c in candidates):
            raise ValueError('expected valid benchmark signatures and string witnesses')
        library = self.library
        library.keys = np.frombuffer(b''.join(c.key for c in candidates), dtype=np.uint8).reshape(-1,49)
        cells = library.keys[:,25:].reshape(-1,6,4)
        library.profiles = cells[:,:,0]
        library.level = cells[:,:,1]
        library.role_masks = (cells[:,:,2].astype(np.uint16) << 8) | cells[:,:,3].astype(np.uint16)
        library.required_role_masks = np.zeros(len(candidates), dtype=np.uint16)
        for i in range(12):
            library.required_role_masks |= (library.keys[:,1+2*i] != 255).astype(np.uint16) << i
        # The stream supplies only classes with a legal grammar derivation
        # within this query's allowed depth. The native verifier handles V2–V4.
        self.variant.eligible = np.ones(len(candidates), dtype=bool)
        self.variant.witnesses = tuple(c.witness for c in candidates)

    def check(self, candidates):
        self._bind_batch(candidates)
        self.native.prepare_batch(range(len(candidates)))
        lawful = []
        for local_id, candidate in enumerate(candidates):
            result = self.native.verify(local_id)
            if result is not None:
                lawful.append(Evidence(candidate.key, candidate.witness, result.actions,
                                       result.cell_surcharges, result.cell_execution_costs))
        return lawful

    def normalized_agreement(self, evidence):
        self._bind_batch((_PublicCandidate(evidence.class_id, evidence.witness),))
        native_evidence = SimpleNamespace(class_id=0, actions=evidence.actions,
                                          cell_surcharges=evidence.cell_surcharges,
                                          cell_execution_costs=evidence.cell_execution_costs)
        # The original implementation re-encodes the witness and checks its
        # real state-machine schedule/costs against the packed evidence.
        return self.native._agreement_witness(native_evidence)

    def b2(self):
        return sorted((_PublicCandidate(self.encoder.encode(Static(profile)), syntax_key(Static(profile)))
                       for profile in self.encoder.public.b2_profiles), key=lambda candidate: candidate.key)


def run_protocol(stream_or_factory, public, private, *, max_depth=2, budgets=(100, 500, 1000, 5000)):
    """Consume exact grammar candidates on demand, with native bilateral negotiation.

    Returns (budget records, protocol events, timings/counters). Use a factory
    to defer constructing the public search cursor until B2 fails. The cursor
    method next_contract() returns an item with bytes key and witness text, or
    None/StopIteration when exhausted. It receives no private/protocol data.
    """
    budgets = tuple(budgets)
    if not budgets or budgets != BUDGETS[:len(budgets)]:
        raise ValueError('fixed V1 budget checkpoints required, including B=1000 if running through 5000')
    started = perf_counter()
    native = _BatchVerifier(public, max_depth, budgets[-1])
    app = PrivateAgent('application', public, private.application)
    net = PrivateAgent('network', public, private.network)
    records, pool, history = {}, [], []
    seen = set()
    winner = None
    representative = None
    counters = dict(complete_candidates_consumed=0, public_search_seconds=0.,
                    verification_seconds=perf_counter()-started, protocol_seconds=0.,
                    witness_seconds=0.)

    def check(candidates):
        before = perf_counter()
        for candidate in candidates:
            if candidate.key in seen:
                raise ValueError('candidate repeated across charged batches')
            seen.add(candidate.key)
        pool.extend(native.check(candidates))
        counters['verification_seconds'] += perf_counter()-before

    def negotiate_current():
        nonlocal winner, history, representative
        before = perf_counter()
        prior = sum(e['message']=='PROPOSE' for e in history)
        if prior >= ROUND_LIMIT:
            return
        winner, history = negotiate(pool, app, net, max_rounds=ROUND_LIMIT-prior, history=history)
        counters['protocol_seconds'] += perf_counter()-before
        if winner is not None:
            before = perf_counter()
            representative = native.normalized_agreement(winner)
            counters['witness_seconds'] += perf_counter()-before

    start_b2 = perf_counter()
    static = native.b2()
    counters['public_search_seconds'] += perf_counter()-start_b2
    for i in range(0,len(static),CHUNK):
        check(static[i:i+CHUNK])
    public_feasible_b2 = len(pool)
    negotiate_current()
    b2_agreement = winner is not None

    def record(budget):
        return dict(agreement=winner is not None,
                    signature=None if winner is None else winner.class_id.hex(),
                    representative=representative, verification_calls=native.native.calls,
                    b2_verification_calls=len(static), b2_agreement=b2_agreement,
                    public_feasible_b2=public_feasible_b2, public_feasible_candidates=len(pool),
                    batch_calls=native.native.batch_calls, batch_candidate_checks=native.native.batch_candidate_checks,
                    proposals=sum(e['message']=='PROPOSE' for e in history))

    if not b2_agreement:
        before = perf_counter()
        stream = stream_or_factory() if callable(stream_or_factory) else stream_or_factory
        counters['public_search_seconds'] += perf_counter()-before
        while native.native.calls < budgets[-1] and winner is None:
            if sum(e['message']=='PROPOSE' for e in history) >= ROUND_LIMIT:
                break
            before = perf_counter()
            batch = []
            limit = min(CHUNK, next(b for b in budgets if b>native.native.calls)-native.native.calls)
            exhausted = False
            for _ in range(limit):
                try:
                    candidate = stream.next_contract()
                except StopIteration:
                    candidate = None
                if candidate is None:
                    exhausted = True
                    break
                batch.append(candidate)
            counters['public_search_seconds'] += perf_counter()-before
            if not batch:
                break
            counters['complete_candidates_consumed'] += len(batch)
            check(batch)
            negotiate_current()
            if native.native.calls in budgets:
                records[native.native.calls] = record(native.native.calls)
            if exhausted:
                break
    for budget in budgets:
        if budget not in records:
            records[budget] = record(budget)
    counters['total_seconds'] = perf_counter()-started
    return records, [dict(e, candidate_id=e['candidate_id'].hex()) for e in history], counters


def reference_utilities(outcomes, instance, max_depth):
    """Post hoc, verify selected witnesses as in the historical V1 harness."""
    values = {}
    for outcome in outcomes.values():
        if not outcome['agreement']:
            continue
        witness = outcome['representative']
        if witness not in values:
            checked = verify_instance(_decode_witness(json.loads(witness)), instance, max_depth)
            if not checked.verified:
                raise ValueError('accepted protocol witness failed independent exact validator')
            a, n = checked.application_utility, checked.network_utility
            values[witness] = dict(uA=a, uN=n, nash=a*n)
        outcome.update(values[witness])
    return outcomes
