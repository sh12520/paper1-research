# Core authorization guard audit-chain migration

The prior independently audited `src/instances.py` SHA256 is recorded in the existing availability-index manifest. This migration adds one exact, fixed-byte authorization guard at the beginning of `derive_seed`: SHADOW and ENGINEERING sampling semantics are unchanged; PILOT/CONFIRM are rejected, and SMOKE must pass namespace authorization before seed hashing or RNG construction. No graph, index, model or distribution is rewritten.

Both execution-snapshot validation and availability-index loading call the same `src.core_authorization_compat.core_source_matches` verifier. It requires the exact CRLF guard exactly once, at the unique `derive_seed` entry, and requires SHA256 of the remaining original bytes to equal the prior manifest/audit digest. Missing, duplicate, relocated or altered guard bytes and any other modification fail closed. The current execution snapshot also binds SHA256 of the entire modified source tree, including the full guard and compatibility helper; stripping is used only to compare the historical audited sampler identity.

Seed-free tests in `tests/test_core_authorization_compat.py` exercise missing, duplicated, altered and additional source changes, as well as absence of digest/RNG calls when SMOKE, PILOT and CONFIRM are denied. Subsequent end-to-end shadow and ENGINEERING regression evidence must be checked separately; this note alone is not experimental confirmation.

## PILOT-ROUTING-CLOSE-01 authorization migration

The fixed entry guard now authorizes PILOT through its separate locked execution-snapshot authorization and continues to hard-deny CONFIRM; SMOKE keeps its own authorization gate. Removing exactly this new guard at the unique `derive_seed` entry still reproduces the originally audited sampler SHA256 byte-for-byte. Both snapshot and availability-index validation use the same strict verifier, which rejects missing, duplicated, relocated, altered or additional core bytes. No graph or availability index was rebuilt, and authorization remains false until explicitly changed.
