import unittest
from unittest.mock import Mock

from sim import LIGHT, MAIN, Release, ResourceHint, Simulation
from test_sim import PROFILE, fixture


class ResourceViewTests(unittest.TestCase):
    def test_ready_head_does_not_wait_for_following_job(self):
        releases = tuple(Release(i, i, 0, "sample") for i in range(2))
        inputs = fixture(deadline=200, releases=releases)
        for causal, expected_grade in ((False, LIGHT), (True, MAIN)):
            with self.subTest(causal=causal):
                sim = Simulation(inputs, "Structured-RDINP", PROFILE,
                                 causal_resource_view=causal)
                for task in sim.tasks:
                    task.client_epoch = task.edge_epoch = 1
                    sim.pending.append((task, 1, MAIN))
                sim.dispatch()
                head, following = sim.tasks
                self.assertEqual(head.edge_started_epoch, 1)
                self.assertEqual(following.edge_started_epoch, 0)
                self.assertEqual(sim.free_at[0], PROFILE["sample"][expected_grade].service)
                self.assertEqual(head.switch_edge, int(expected_grade == LIGHT))

    def test_terminal_uses_reply_snapshot_in_both_directions(self):
        for hinted_wait, live_wait, expected_grade in ((0, 120, MAIN), (80, 0, LIGHT)):
            with self.subTest(hinted_wait=hinted_wait, live_wait=live_wait):
                sim = Simulation(fixture(deadline=200), "Structured-RDINP", PROFILE,
                                 causal_resource_view=True)
                task, = sim.tasks
                task.client_epoch = task.edge_epoch = 1
                sim.clock.now = 8
                sim.free_at[0] = sim.clock.now + live_wait
                sim.send_input = Mock()
                hint = ResourceHint(hinted_wait, 0, 0, 0, False)
                sim.on_receipt(task, 1, MAIN, True, hint=hint)
                sim.clock.run()
                sim.send_input.assert_called_once_with(task, 1, expected_grade)
                self.assertEqual(task.switch_upload, int(expected_grade == LIGHT))

    def test_cache_activation_requires_delivered_receipt(self):
        for delivered in (False, True):
            with self.subTest(delivered=delivered):
                sim = Simulation(fixture(), "Reactive-ReNeg", PROFILE,
                                 causal_resource_view=True)
                task, = sim.tasks
                task.client_epoch = task.edge_epoch = 2
                sim.network.send = Mock()
                hint = ResourceHint(0, 0, 0, 0, True)
                sim.on_receipt(task, 2, LIGHT, delivered, hint=hint)
                sim.clock.run()
                if delivered:
                    sim.network.send.assert_called_once()
                    self.assertEqual(sim.network.send.call_args.args[:5],
                                     (task, "up", 64, True, sim.cutoff(task)))
                else:
                    sim.network.send.assert_not_called()
                self.assertEqual(task.edge_started_epoch, 0)


if __name__ == "__main__":
    unittest.main()
