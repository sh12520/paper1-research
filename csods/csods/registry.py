"""Public capability registry for the first experimental grammar.

Predicate and effect strings are identifiers, not executable expressions. The
validator/compiler must implement them against public network state. Costs are
illustrative benchmark inputs, not measurements of a deployed network.
"""
from .models import Capability


def _cap(id, provider, inputs, outputs, preconditions, effects, costs, execution_cost, scopes):
    return Capability(id, provider, tuple(inputs), tuple(outputs), tuple(preconditions),
                      tuple(effects), dict(costs), execution_cost, tuple(scopes))


def default_registry() -> dict[str, Capability]:
    """Return a fresh registry; callers can remove entries for controls."""
    caps = [
        _cap('observe_motion_state', 'application', [], ['MotionState'], ['motion_observable'], ['observe_motion'], {}, .01, ['conditional']),
        _cap('set_quality', 'application', ['Quality'], ['Action'], ['quality_supported'], ['set_quality'], {}, .01, ['static', 'conditional', 'phased', 'delayed', 'validity', 'offload']),
        _cap('select_latency_profile', 'network', ['Deadline'], ['Action'], ['deadline_supported'], ['select_latency'], {}, .01, ['static', 'conditional', 'phased', 'delayed', 'validity', 'offload']),
        _cap('set_rate', 'network', ['Rate'], ['Action'], ['rate_supported'], ['set_rate'], {}, .01, ['static', 'conditional', 'phased', 'delayed', 'validity', 'offload']),
        _cap('schedule_start', 'application', ['Offset'], ['Action'], ['scheduling_supported'], ['schedule_start'], {}, .01, ['delayed']),
        _cap('set_validity_interval', 'network', ['Interval'], ['Action'], ['validity_supported'], ['set_validity'], {}, .01, ['validity']),
        _cap('apply_conditional_policy', 'network', ['Condition', 'Clause', 'Clause'], ['Action'], ['conditional_supported'], ['conditional_policy'], {}, .02, ['conditional']),
        _cap('apply_phased_policy', 'network', ['Duration', 'Clause', 'Clause'], ['Action'], ['phasing_supported'], ['phased_policy'], {}, .02, ['phased']),
        _cap('enable_edge_offload', 'edge', ['Level'], ['Action'], ['offload_supported'], ['edge_offload'], {'EDGE': .1}, .02, ['offload']),
        _cap('reserve_ran_resource', 'ran', ['ResourceAmount'], ['Reservation'], ['ran_reservation_supported'], ['reserve_ran'], {}, .01, ['static', 'conditional', 'phased', 'delayed', 'validity', 'offload']),
        _cap('reserve_fh_resource', 'fh', ['ResourceAmount'], ['Reservation'], ['fh_reservation_supported'], ['reserve_fh'], {}, .01, ['static', 'conditional', 'phased', 'delayed', 'validity', 'offload']),
        _cap('reserve_edge_compute', 'edge', ['ResourceAmount'], ['Reservation'], ['edge_reservation_supported'], ['reserve_edge'], {}, .01, ['offload']),
    ]
    return {cap.id: cap for cap in caps}
