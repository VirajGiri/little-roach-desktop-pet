import unittest

from pet_core import (PetSettings, approach_angle, choose_target, forward_crawl_step,
                      gait_pose, movement_step)


class FixedRandom:
    def __init__(self, values):
        self.values = iter(values)

    def random(self):
        return next(self.values)

    def randint(self, low, high):
        return low


class PetCoreTests(unittest.TestCase):
    def test_settings_are_clamped_to_supported_ranges(self):
        settings = PetSettings.from_dict({"speed": 99, "scale": 0, "start_with_windows": True})
        self.assertEqual((settings.speed, settings.scale, settings.start_with_windows), (3.0, 0.7, True))

    def test_local_target_stays_inside_virtual_screen(self):
        x, y = choose_target(-900, 100, (-1920, 0, 3000, 1080), 112, 96, 1,
                             FixedRandom([0.9]))
        self.assertGreaterEqual(x, -1920)
        self.assertLessEqual(x, -1920 + 3000 - 112)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(y, 1080 - 96)

    def test_long_trip_uses_entire_screen(self):
        # First random chooses the long-trip branch; randint returns each lower bound.
        x, y = choose_target(500, 300, (0, 0, 1920, 1080), 112, 96, 1,
                             FixedRandom([0.1]))
        self.assertEqual((x, y), (0, 0))

    def test_heading_turns_across_zero_by_shortest_arc(self):
        self.assertAlmostEqual(approach_angle(350, 10, 5), 355)
        self.assertAlmostEqual(approach_angle(5, 355, 5), 0)

    def test_gait_frames_follow_distance_and_loop(self):
        self.assertEqual([gait_pose(step * 5) for step in range(16)], list(range(16)))
        self.assertEqual(gait_pose(80), 0)
        self.assertEqual(gait_pose(85), 1)

    def test_movement_distance_is_independent_of_frame_interval(self):
        self.assertAlmostEqual(movement_step(4.0, 0.016), 1.6)
        self.assertAlmostEqual(movement_step(4.0, 0.04), 4.0)

    def test_roach_turns_in_place_before_moving_forward(self):
        self.assertEqual(forward_crawl_step(0, 20, 0, 3), (0.0, 0.0, False))
        dx, dy, moving = forward_crawl_step(20, 0, 0, 3)
        self.assertTrue(moving)
        self.assertAlmostEqual(dx, 3)
        self.assertAlmostEqual(dy, 0)

    def test_crawl_step_follows_heading_without_sideways_sliding(self):
        dx, dy, moving = forward_crawl_step(100, 100, 45, 4)
        self.assertTrue(moving)
        self.assertAlmostEqual(dx, dy)
        self.assertAlmostEqual((dx * dx + dy * dy) ** 0.5, 4)


if __name__ == "__main__":
    unittest.main()
