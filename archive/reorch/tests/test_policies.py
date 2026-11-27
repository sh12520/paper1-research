import unittest
from types import SimpleNamespace
from unittest.mock import patch

from models import Profile, Instance
from policies import POLICIES
from policies.common import partitions


def state(ids="ABCD"):
    return SimpleNamespace(
        active=tuple(ids), deadlines={s: 10 for s in ids}, time=0,
        ledger=(0, 0, 0), capacity=(100, 100, 100),
        profiles={s: (Profile((20, 20, 20), 0),) for s in ids},
        indices={s: 0 for s in ids}, kappa=0, history=[], initial_partition=None,
    )


class PolicyTests(unittest.TestCase):
    def test_enumerates_bell_number_and_exact_cover(self):
        candidates = list(partitions("ABCD"))
        self.assertEqual(len(candidates), 15)
        self.assertEqual(len(set(candidates)), 15)
        for candidate in candidates:
            flattened = [s for group in candidate for s in group]
            self.assertEqual(sorted(flattened), list("ABCD"))

    def test_b3_checks_every_partition_once_and_stays_static(self):
        s = state()
        policy = POLICIES["B3"]()
        with patch("negotiation_engine.evaluate_partition", side_effect=lambda st, p: -len(p)) as evaluate:
            original = policy.select(s)
            self.assertEqual(evaluate.call_count, 15)
            self.assertEqual(original, [("A", "B", "C", "D")])
            s.active = ("A", "C", "D")
            self.assertEqual(policy.select(s), [("A", "C", "D")])
            self.assertEqual(evaluate.call_count, 15)

    def test_symmetric_cluster_permutation_invariance(self):
        first = state("ABCD")
        second = state("DCBA")
        partition1 = POLICIES["B2"]().select(first)
        partition2 = POLICIES["B2"]().select(second)
        self.assertEqual({frozenset(g) for g in partition1}, {frozenset(g) for g in partition2})
        self.assertEqual({frozenset(g) for g in partition1}, {frozenset("ABCD")})

    def test_sequential_holds_session_until_exit(self):
        s = state()
        s.deadlines.update(A=12, B=8, C=10, D=6)
        policy = POLICIES["B0"]()
        self.assertEqual(policy.select(s), [("D",)])
        s.deadlines["A"] = 1
        self.assertEqual(policy.select(s), [("D",)])
        s.active = ("A", "B", "C")
        self.assertEqual(policy.select(s), [("A",)])

    def test_concurrent_tracks_active(self):
        s = state()
        policy = POLICIES["B1"]()
        self.assertEqual(policy.select(s), [("A", "B", "C", "D")])
        s.active = ("B", "D")
        self.assertEqual(policy.select(s), [("B", "D")])

    def test_symmetric_engine_outcomes_under_relabeling(self):
        from negotiation_engine import simulate
        def symmetric(ids):
            return Instance(
                seed=1, family="STATIC_COUPLING", strength="weak", tightness="medium",
                capacity=(50, 50, 50),
                profiles={s: tuple(Profile((n, n, n), k) for k, n in enumerate((20, 15, 10))) for s in ids},
                utilities={s: (1.0, .9, .8) for s in ids},
                deadlines={s: 8 for s in ids}, reservation={s: .8 for s in ids},
                aspiration_start={s: 1.05 for s in ids},
            )
        keys = ("welfare", "completion_rate", "deadline_miss_rate", "wall_time", "rounds", "messages", "rejected_at_commit")
        for method in POLICIES:
            with self.subTest(method=method):
                a = simulate(symmetric("ABCD"), method, .15)
                b = simulate(symmetric("WXYZ"), method, .15)
                self.assertEqual(tuple(a[k] for k in keys), tuple(b[k] for k in keys))


if __name__ == "__main__":
    unittest.main()
