import unittest

from setpiece import corners

FPS = 25.0


def crowd(corner_x, count, at_corner=True):
    """A frame: `count` people in the penalty area, optionally a corner taker."""
    people = []
    if at_corner:
        people.append((99, "right", "player", corner_x * 0.999, -34.0))
    for n in range(count):
        x = corner_x - 8.0 if corner_x > 0 else corner_x + 8.0
        people.append((n, "left" if n % 2 else "right", "player", x, -10.0 + n))
    return people


def half(shape_frames, total=1000, **kwargs):
    """Frames 1..total, with `shape_frames` looking like a corner."""
    frames = {}
    for frame in range(1, total + 1):
        frames[frame] = (crowd(52.5, 12, **kwargs) if frame in shape_frames
                         else crowd(52.5, 2, at_corner=False))
    return frames


class ShapeTest(unittest.TestCase):
    def test_a_crowded_box_with_a_taker_is_a_corner(self):
        found = corners.candidates(half(set(range(100, 200))), FPS)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].event, "corner")

    def test_a_crowded_box_without_a_taker_is_not(self):
        self.assertEqual(corners.candidates(half(set(range(100, 200)), at_corner=False), FPS), [])

    def test_a_taker_without_a_crowd_is_not(self):
        frames = {frame: crowd(52.5, 3) for frame in range(1, 500)}
        self.assertEqual(corners.candidates(frames, FPS), [])

    def test_the_far_corner_does_not_count_the_near_box(self):
        # Everyone is in the right-hand box; the taker stands at a left corner.
        people = crowd(52.5, 12, at_corner=False)
        people.append((99, "right", "player", -52.5, -34.0))
        self.assertEqual(corners.candidates({f: people for f in range(1, 500)}, FPS), [])


class TimingTest(unittest.TestCase):
    def test_a_situation_is_timed_at_its_end_not_its_middle(self):
        found = corners.candidates(half(set(range(100, 351))), FPS)
        # The scan visits every fifth frame at the default 5 fps, so the
        # reported end may sit up to one scan interval before the true one.
        self.assertAlmostEqual(found[0].time, 350 / FPS, delta=1 / 5.0)
        self.assertGreater(found[0].time, (100 + 350) / 2 / FPS)

    def test_a_brief_interruption_stays_one_candidate(self):
        shape = set(range(100, 200)) | set(range(350, 400))  # 6 s gap
        self.assertEqual(len(corners.candidates(half(shape), FPS)), 1)

    def test_a_long_separation_is_two_candidates(self):
        shape = set(range(100, 200)) | set(range(900, 1000))  # 28 s gap
        self.assertEqual(len(corners.candidates(half(shape, total=1200), FPS)), 2)

    def test_confidence_rises_with_how_long_the_shape_held(self):
        brief = corners.candidates(half(set(range(100, 120))), FPS)[0]
        long = corners.candidates(half(set(range(100, 500))), FPS)[0]
        self.assertGreater(long.confidence, brief.confidence)


class SettingsTest(unittest.TestCase):
    def test_a_stricter_crowd_threshold_rejects_a_thin_box(self):
        frames = half(set(range(100, 300)))
        self.assertEqual(len(corners.candidates(frames, FPS)), 1)
        strict = corners.Settings(min_in_box=14)
        self.assertEqual(corners.candidates(frames, FPS, strict), [])

    def test_impossible_settings_are_refused(self):
        for bad in ({"corner_radius": 0}, {"scan_fps": -1}, {"min_in_box": 0}, {"merge_gap": 0}):
            with self.assertRaises(ValueError, msg=bad):
                corners.Settings(**bad)

    def test_no_frames_is_no_candidates(self):
        self.assertEqual(corners.candidates({}, FPS), [])
