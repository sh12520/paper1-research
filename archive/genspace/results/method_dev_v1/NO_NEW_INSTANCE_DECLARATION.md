# Development data and randomization boundary

The development harness reads only the 1,920 previously serialized PILOT instances. It replaces `src.instances.generate_instance` and `src.instances.derive_seed` with functions that raise if called, and records their invocation counts. No new benchmark instance or benchmark instance seed is generated.

RANDOM-BUDGET requires method randomization: its candidate permutation uses a deterministic PRNG input derived from only the allowlisted public view. This is a method-level ordering seed, not a new instance seed. It does not use family, pressure/conflict labels, instance identifiers, private hashes, preferences, or oracle outcomes.

Original PILOT artifacts and the abstract benchmark are read-only. CONFIRM remains disabled and no FROZEN_CONFIG.yaml is created. Results in this directory are development evidence, not confirmation evidence.
