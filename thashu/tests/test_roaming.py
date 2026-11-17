import unittest

from core.decision import get_roaming_command
from core.roaming import is_clear, select_roaming_action


def sensors(left=900, center=900, right=900, rear=900):
    return {"tof_left_mm": left, "tof_center_mm": center,
            "tof_right_mm": right, "rear_mm": rear}


class RoamingPolicyTests(unittest.TestCase):
    def test_voice_commands_are_exact_and_deterministic(self):
        self.assertEqual(get_roaming_command("Start roaming!"), "START")
        self.assertEqual(get_roaming_command("stop roaming mode"), "STOP")
        self.assertIsNone(get_roaming_command("tell me about roaming"))

    def test_clearance_threshold(self):
        self.assertFalse(is_clear(300))
        self.assertTrue(is_clear(301))
        self.assertTrue(is_clear("FAR"))

    def test_invalid_values_fail_closed(self):
        for value in (None, "UNKNOWN", float("nan"), float("inf"), True):
            with self.subTest(value=value):
                self.assertFalse(is_clear(value))

    def test_missing_snapshot_stays_stopped(self):
        self.assertEqual(select_roaming_action(None), (None, 0, 0, "sensor_unavailable"))

    def test_clear_front_gets_one_bounded_forward_decision(self):
        self.assertEqual(select_roaming_action(sensors()), ("FORWARD", 1, 0, "front_clear"))

    def test_random_turn_after_fourth_clear_evaluation(self):
        self.assertEqual(
            select_roaming_action(sensors(), forward_pulses=3, choose=lambda _: "RIGHT"),
            ("RIGHT", 0, 0, "periodic_turn"),
        )

    def test_blocked_front_reverses_at_most_twice_with_clear_rear(self):
        obstacle = sensors(center=250)
        self.assertEqual(select_roaming_action(obstacle),
                         ("BACKWARD", 0, 1, "front_blocked_reverse"))
        self.assertEqual(select_roaming_action(obstacle, reverse_attempts=1),
                         ("BACKWARD", 0, 2, "front_blocked_reverse"))

    def test_blocked_rear_means_no_reverse(self):
        self.assertIsNone(select_roaming_action(sensors(center=250, rear=300))[0])

    def test_after_reverse_limit_selects_clearer_side(self):
        self.assertEqual(
            select_roaming_action(sensors(left=650, center=250, right=400), reverse_attempts=2),
            ("LEFT", 0, 2, "clearer_side"),
        )

    def test_no_clear_route_stays_stopped(self):
        self.assertIsNone(select_roaming_action(
            sensors(left=250, center=250, right=250, rear=250), reverse_attempts=2
        )[0])


if __name__ == "__main__":
    unittest.main()
