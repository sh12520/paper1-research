# PILOT depth and richness

PILOT exploratory description only; not confirmation evidence. No research Gate A–E determination is made. All rates are per-instance; B1 deadlock resolution has a B1-deadlock denominator, and NA denotes an empty denominator. B0/B1/B2/O1 comparisons are paired on each serialized instance. Nash welfare and per-agent utility means are computed among instances where the method reaches agreement; failures are excluded, not treated as zero.

Seed derivation includes the complete configuration: matching seed indices across depth/richness are distinct random instances. These are group descriptions, not within-instance paired or causal contrasts; the requested count of depth-2-only resolved identical instances is not identifiable from this design.

## Depth

| family | composition_depth | n | O1_rate | resolution_rate | structural_agreement_count |
| --- | --- | --- | --- | --- | --- |
| F1 | 1 | 240 | 0.7292 | 0.7018 | 154 |
| F1 | 2 | 240 | 0.7875 | 0.7650 | 164 |
| F2 | 1 | 240 | 0.2042 | 0.2042 | 49 |
| F2 | 2 | 240 | 0.3042 | 0.3042 | 73 |
| F3 | 1 | 240 | 0.7000 | 0.6814 | 154 |
| F3 | 2 | 240 | 0.7125 | 0.6776 | 155 |
| F4 | 1 | 240 | 0.7125 | 0.6920 | 151 |
| F4 | 2 | 240 | 0.7333 | 0.7037 | 160 |

## Richness

| family | capability_richness | n | O1_rate | resolution_rate | structural_agreement_count |
| --- | --- | --- | --- | --- | --- |
| F1 | rich | 240 | 0.8917 | 0.8839 | 206 |
| F1 | sparse | 240 | 0.6250 | 0.5735 | 112 |
| F2 | rich | 240 | 0.3500 | 0.3500 | 84 |
| F2 | sparse | 240 | 0.1583 | 0.1583 | 38 |
| F3 | rich | 240 | 0.9000 | 0.8914 | 214 |
| F3 | sparse | 240 | 0.5125 | 0.4658 | 95 |
| F4 | rich | 240 | 0.8583 | 0.8475 | 203 |
| F4 | sparse | 240 | 0.5875 | 0.5438 | 108 |

Mechanism labels across all O1 agreements, by family and richness (labels may overlap):

| family | richness | mechanism | selected_count | denominator |
| --- | --- | --- | --- | --- |
| F1 | sparse | STATIC | 38 | 150 |
| F1 | sparse | STATE_CONDITIONAL | 13 | 150 |
| F1 | sparse | DELAYED_START | 0 | 150 |
| F1 | sparse | TEMPORAL_PHASED | 0 | 150 |
| F1 | sparse | OFFLOAD | 103 | 150 |
| F1 | sparse | HYBRID | 4 | 150 |
| F1 | rich | STATIC | 8 | 214 |
| F1 | rich | STATE_CONDITIONAL | 9 | 214 |
| F1 | rich | DELAYED_START | 0 | 214 |
| F1 | rich | TEMPORAL_PHASED | 0 | 214 |
| F1 | rich | OFFLOAD | 206 | 214 |
| F1 | rich | HYBRID | 9 | 214 |
| F2 | sparse | STATIC | 0 | 38 |
| F2 | sparse | STATE_CONDITIONAL | 0 | 38 |
| F2 | sparse | DELAYED_START | 0 | 38 |
| F2 | sparse | TEMPORAL_PHASED | 4 | 38 |
| F2 | sparse | OFFLOAD | 38 | 38 |
| F2 | sparse | HYBRID | 4 | 38 |
| F2 | rich | STATIC | 0 | 84 |
| F2 | rich | STATE_CONDITIONAL | 0 | 84 |
| F2 | rich | DELAYED_START | 1 | 84 |
| F2 | rich | TEMPORAL_PHASED | 19 | 84 |
| F2 | rich | OFFLOAD | 84 | 84 |
| F2 | rich | HYBRID | 20 | 84 |
| F3 | sparse | STATIC | 28 | 123 |
| F3 | sparse | STATE_CONDITIONAL | 0 | 123 |
| F3 | sparse | DELAYED_START | 0 | 123 |
| F3 | sparse | TEMPORAL_PHASED | 12 | 123 |
| F3 | sparse | OFFLOAD | 84 | 123 |
| F3 | sparse | HYBRID | 1 | 123 |
| F3 | rich | STATIC | 2 | 216 |
| F3 | rich | STATE_CONDITIONAL | 0 | 216 |
| F3 | rich | DELAYED_START | 0 | 216 |
| F3 | rich | TEMPORAL_PHASED | 4 | 216 |
| F3 | rich | OFFLOAD | 214 | 216 |
| F3 | rich | HYBRID | 4 | 216 |
| F4 | sparse | STATIC | 33 | 141 |
| F4 | sparse | STATE_CONDITIONAL | 0 | 141 |
| F4 | sparse | DELAYED_START | 0 | 141 |
| F4 | sparse | TEMPORAL_PHASED | 0 | 141 |
| F4 | sparse | OFFLOAD | 108 | 141 |
| F4 | sparse | HYBRID | 0 | 141 |
| F4 | rich | STATIC | 3 | 206 |
| F4 | rich | STATE_CONDITIONAL | 0 | 206 |
| F4 | rich | DELAYED_START | 0 | 206 |
| F4 | rich | TEMPORAL_PHASED | 0 | 206 |
| F4 | rich | OFFLOAD | 203 | 206 |
| F4 | rich | HYBRID | 0 | 206 |

## Pressure

| family | resource_pressure | n | O1_rate | resolution_rate | o1_minus_b2 |
| --- | --- | --- | --- | --- | --- |
| F1 | high | 160 | 0.5312 | 0.5312 | 0.5312 |
| F1 | low | 160 | 0.9500 | 0.9441 | 0.3125 |
| F1 | medium | 160 | 0.7937 | 0.7500 | 0.6187 |
| F2 | high | 160 | 0.0063 | 0.0063 | 0.0063 |
| F2 | low | 160 | 0.5062 | 0.5062 | 0.5062 |
| F2 | medium | 160 | 0.2500 | 0.2500 | 0.2500 |
| F3 | high | 160 | 0.5250 | 0.5250 | 0.5250 |
| F3 | low | 160 | 0.8438 | 0.8264 | 0.4813 |
| F3 | medium | 160 | 0.7500 | 0.7059 | 0.6000 |
| F4 | high | 160 | 0.5312 | 0.5283 | 0.5250 |
| F4 | low | 160 | 0.8562 | 0.8345 | 0.2375 |
| F4 | medium | 160 | 0.7812 | 0.7535 | 0.6687 |

## Conflict

| family | preference_conflict | n | O1_rate | resolution_rate | o1_minus_b2 |
| --- | --- | --- | --- | --- | --- |
| F1 | high | 240 | 0.6417 | 0.6417 | 0.5458 |
| F1 | medium | 240 | 0.8750 | 0.8462 | 0.4292 |
| F2 | high | 240 | 0.0958 | 0.0958 | 0.0958 |
| F2 | medium | 240 | 0.4125 | 0.4125 | 0.4125 |
| F3 | high | 240 | 0.5917 | 0.5917 | 0.5500 |
| F3 | medium | 240 | 0.8208 | 0.7850 | 0.5208 |
| F4 | high | 240 | 0.5875 | 0.5875 | 0.5042 |
| F4 | medium | 240 | 0.8583 | 0.8300 | 0.4500 |
