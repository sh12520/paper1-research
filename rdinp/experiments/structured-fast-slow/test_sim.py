import unittest

from sim import (
    AIR_RATES, LIGHT, LOCAL, MAIN, METHODS, MISSED, Clock, Inputs, Network,
    Release, Scenario, Simulation, Tier, paired_inputs,
)

PROFILE = {
    "sample": {
        MAIN: Tier(1000, 1000, 80, 0, 1),
        LIGHT: Tier(500, 500, 30, 0, .7),
        LOCAL: Tier(0, 0, 10, 0, .5),
    },
}
CAPACITY = ((0.0, 2250.0), (2000.0, 1000.0), (3000.0, 2250.0))


def fixture(deadline=300, bad=False, releases=None):
    channel = {direction: ((bad, 0.0),) * 200 for direction in AIR_RATES}
    if releases is None:
        releases = (Release(0, 0, 0, "sample"),)
    return Inputs(Scenario(.7, 0, .5, deadline), releases, CAPACITY, channel, 1, "fixture")


class SimulationTests(unittest.TestCase):
    def test_trace_rollover_and_boundary_service(self):
        link = Network(Clock(), fixture())
        self.assertEqual(link.rate("fh", 2000)[0], 1000)
        self.assertEqual(link.rate("fh", 5000)[0], 2250)
        self.assertEqual(link.rate("up", 2000)[0], 12)
        self.assertAlmostEqual(link.end_of_frame("up", 1999, 4500), 2001)

    def test_no_fault_can_adopt_every_method(self):
        for method in METHODS:
            task, = Simulation(fixture(), method, PROFILE).run()
            self.assertEqual(task.grade, MAIN, method)
            self.assertEqual(task.rounds, 2, method)
            self.assertEqual(task.edge_epoch, task.edge_started_epoch)
            self.assertGreater(task.control_bytes, 0)

    def test_burst_retries_cost_and_no_execution_without_receipt(self):
        for method in METHODS:
            task, = Simulation(fixture(bad=True), method, PROFILE).run()
            self.assertEqual(task.lost_frames, 3, method)
            self.assertEqual(task.air_attempts, 3)
            self.assertEqual(task.edge_started_epoch, 0)
            self.assertEqual(task.grants, 0)
            self.assertEqual(task.grade, MISSED if method == METHODS[0] else LOCAL)

    def test_tight_window_offers_light_without_second_negotiation(self):
        structured, = Simulation(fixture(145), METHODS[3], PROFILE).run()
        reactive, = Simulation(fixture(145), METHODS[1], PROFILE).run()
        static, = Simulation(fixture(145), METHODS[2], PROFILE).run()
        self.assertEqual(structured.grade, LIGHT)
        self.assertEqual(reactive.grade, LIGHT)
        self.assertEqual(static.grade, LOCAL)
        self.assertLess(structured.rounds, reactive.rounds)
        self.assertEqual(structured.requests, 1)
        self.assertEqual(reactive.requests, 2)

    def test_strict_deadline_and_immutable_fallback_output(self):
        sim = Simulation(fixture(), METHODS[3], PROFILE)
        task = sim.tasks[0]
        task.client_epoch = task.edge_epoch = 1
        sim.clock.now = task.fallback
        sim.fallback(task)
        sim.receive_result(task, 1, MAIN, True)
        sim.clock.run()
        self.assertEqual(task.grade, LOCAL)
        self.assertEqual(task.stale_results, 1)
        sim = Simulation(fixture(), METHODS[0], PROFILE)
        task = sim.tasks[0]
        sim.clock.now = task.deadline
        sim.receive_result(task, 0, MAIN, True)
        self.assertEqual(task.grade, MISSED)

    def test_generation_guard_rejects_old_result(self):
        sim = Simulation(fixture(), METHODS[1], PROFILE)
        task = sim.tasks[0]
        task.client_epoch = task.edge_epoch = 2
        sim.receive_result(task, 1, MAIN, True)
        self.assertIsNone(task.adopted)
        sim.receive_result(task, 2, LIGHT, True)
        self.assertEqual(task.grade, LIGHT)

    def test_pairing_recreates_exogenous_input_and_is_order_independent(self):
        first = paired_inputs(Scenario(.7, .05, .5, 600), 3, CAPACITY, ("sample",), 500, 8, 2)
        second = paired_inputs(Scenario(.7, .05, .5, 600), 3, CAPACITY, ("sample",), 500, 8, 2)
        self.assertEqual(first, second)
        outcomes = []
        for methods in (METHODS, tuple(reversed(METHODS))):
            outcomes.append({m: Simulation(first, m, PROFILE).run() for m in methods})
        self.assertEqual(*outcomes)

    def test_one_slot_busy_time_from_independent_tasks(self):
        releases = tuple(Release(i, i, i * 4, "sample") for i in range(3))
        sim = Simulation(fixture(deadline=340, releases=releases), METHODS[2], PROFILE)
        rows = sim.run()
        self.assertEqual(sum(row.busy for row in rows), 2)
        self.assertEqual(sim.edge_busy_ms, 3 * PROFILE["sample"][MAIN].service)
        self.assertEqual([row.grade for row in rows], [MAIN] * 3)


if __name__ == "__main__":
    unittest.main()
