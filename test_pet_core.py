import unittest

from pet_core import PetSettings, choose_target


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


if __name__ == "__main__":
    unittest.main()
