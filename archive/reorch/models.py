from dataclasses import dataclass

@dataclass(frozen=True)
class Profile:
    demand: tuple
    rank: int

@dataclass(frozen=True)
class Instance:
    seed: int
    family: str
    strength: str
    tightness: str
    capacity: tuple
    profiles: dict
    utilities: dict
    deadlines: dict
    reservation: dict
    aspiration_start: dict
