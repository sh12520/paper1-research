"""A small hand-authored public fixture for a checkout-only demonstration."""

from dataclasses import asdict

from .instances import PublicInstance, digest, load_model_config
from .models import Profile
from .registry import default_registry


def public_example(*, conditional=False):
    model = load_model_config()["model_draft"]
    profiles = (Profile(0.4, 1.0, 0.5), Profile(0.8, 1.0, 0.5))
    registry = {role: asdict(cap) for role, cap in default_registry().items()}
    states = tuple(model["states"])
    horizon = model["horizon"]
    return PublicInstance(
        family="example",
        configuration={"composition_depth": 2},
        horizon=horizon,
        states=states,
        capacity=tuple(
            (tick, state, 0.65 if state == "moving" else 1.0, 1.0, 0.9)
            for tick in range(horizon)
            for state in states
        ),
        m0_profiles=profiles[-1:],
        mr_profiles=profiles,
        b2_profiles=profiles,
        capabilities=tuple(sorted(registry)),
        conditions=("moving",) if conditional else (),
        durations=(),
        offsets=(1,),
        intervals=(),
        offload_levels=("edge",),
        public_constraints=dict(model["public_hard_constraints"]),
        resource_parameters=dict(model["demand"]),
        registry=registry,
        model_config_hash=digest(model),
    )
