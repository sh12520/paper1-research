"""Public, declarative contract and capability data models.

Acceptance preferences are deliberately separate from the public grammar and
registry.  Types here describe values; validators must still check them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, TypeAlias


@dataclass(frozen=True)
class Profile:
    quality: float
    deadline: float
    rate: float


@dataclass(frozen=True)
class Static:
    profile: Profile


@dataclass(frozen=True)
class If:
    condition: str
    then_clause: Clause
    else_clause: Clause


@dataclass(frozen=True)
class Sequence:
    duration: int
    first: Clause
    second: Clause


@dataclass(frozen=True)
class Delay:
    offset: int
    clause: Clause


@dataclass(frozen=True)
class ValidFor:
    interval: tuple[int, int]
    clause: Clause


@dataclass(frozen=True)
class Offload:
    level: str
    clause: Clause


Clause: TypeAlias = Static | If | Sequence | Delay | ValidFor | Offload


@dataclass(frozen=True)
class Capability:
    id: str
    provider: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    preconditions: tuple[str, ...]
    effects: tuple[str, ...]
    resource_cost: Mapping[str, float]
    execution_cost: float
    supported_scope: tuple[str, ...]


@dataclass(frozen=True)
class ApplicationPreferences:
    quality_weight: float
    latency_weight: float
    start_delay_weight: float
    switching_penalty: float
    reservation: float


@dataclass(frozen=True)
class NetworkPreferences:
    ran_cost: float
    fh_cost: float
    edge_cost: float
    policy_complexity_cost: float
    actuation_switching_cost: float
    reservation: float


@dataclass(frozen=True)
class PrivatePreferences:
    application: ApplicationPreferences
    network: NetworkPreferences
