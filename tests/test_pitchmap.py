import unittest

try:
    import numpy as np
    from setpiece import pitchmap
except ImportError:  # pragma: no cover
    np = None


@unittest.skipIf(np is None, "numpy is not installed")
class FitTest(unittest.TestCase):
    """A known distortion is invented, then recovered from points alone."""

    SCALE = (4096.0, 1080.0)

    def truth(self, image_points):
        """Pitch metres from image pixels, with a curve a homography cannot fit."""
        points = np.asarray(image_points, float)
        u = points[:, 0] / self.SCALE[0] * 2 - 1
        v = points[:, 1] / self.SCALE[1] * 2 - 1
        x = 52.5 * u + 6.0 * u * v + 2.0 * u ** 3
        y = 34.0 * v - 4.0 * u ** 2
        return np.column_stack([x, y])

    def sample(self, count, seed=0):
        rng = np.random.default_rng(seed)
        image = np.column_stack([rng.uniform(0, self.SCALE[0], count),
                                 rng.uniform(0, self.SCALE[1], count)])
        return image, self.truth(image)

    def test_recovers_a_curved_mapping(self):
        image, pitch = self.sample(400)
        model = pitchmap.fit(image, pitch, degree=3)
        rmse, _ = pitchmap.error(model, *self.sample(200, seed=1))
        self.assertLess(rmse, 0.05)

    def test_a_first_order_fit_cannot_and_says_so_in_its_error(self):
        image, pitch = self.sample(400)
        linear = pitchmap.fit(image, pitch, degree=1)
        cubic = pitchmap.fit(image, pitch, degree=3)
        held_out = self.sample(200, seed=1)
        self.assertGreater(pitchmap.error(linear, *held_out)[0],
                           10 * pitchmap.error(cubic, *held_out)[0])

    def test_too_few_points_is_refused(self):
        image, pitch = self.sample(5)
        with self.assertRaises(pitchmap.FitError):
            pitchmap.fit(image, pitch, degree=3)

    def test_mismatched_sets_are_refused(self):
        image, pitch = self.sample(40)
        with self.assertRaises(pitchmap.FitError):
            pitchmap.fit(image, pitch[:20], degree=2)


@unittest.skipIf(np is None, "numpy is not installed")
class AlignmentTest(FitTest):
    def frames(self, count=30, people=20, clutter=3, missing=2, seed=3):
        """Frames where the two sets are shuffled, incomplete and cluttered."""
        rng = np.random.default_rng(seed)
        out = []
        for _ in range(count):
            image = np.column_stack([rng.uniform(200, self.SCALE[0] - 200, people),
                                     rng.uniform(200, self.SCALE[1] - 200, people)])
            pitch = self.truth(image)
            # The detector misses some players and finds people who are not
            # players; the annotation has neither problem.
            seen = image[missing:]
            extra = np.column_stack([rng.uniform(0, self.SCALE[0], clutter),
                                     rng.uniform(0, 200, clutter)])
            seen = np.vstack([seen, extra])
            rng.shuffle(seen)
            out.append((seen, pitch))
        return out

    def test_finds_the_mapping_without_being_told_the_correspondence(self):
        model, history = pitchmap.fit_by_alignment(self.frames(), degree=3, cutoff=20.0)
        rmse, _ = pitchmap.error(model, *self.sample(200, seed=9))
        self.assertLess(rmse, 0.5, f"history: {history}")

    def test_the_fit_improves_as_it_goes(self):
        _, history = pitchmap.fit_by_alignment(self.frames(), degree=3, cutoff=20.0)
        self.assertLess(history[-1]["rmse"], history[0]["rmse"])

    def test_no_frames_is_refused(self):
        with self.assertRaises(pitchmap.FitError):
            pitchmap.fit_by_alignment([])


@unittest.skipIf(np is None, "numpy is not installed")
class OnPitchTest(unittest.TestCase):
    def test_keeps_the_pitch_and_a_margin_around_it(self):
        kept = pitchmap.on_pitch([(0, 0), (52.5, 34.0), (60.0, 40.0)])
        self.assertTrue(kept.all())

    def test_drops_what_the_polynomial_invented(self):
        kept = pitchmap.on_pitch([(0, -649.4), (-83.8, 0), (0, 0)])
        self.assertEqual(kept.tolist(), [False, False, True])

    def test_the_margin_is_adjustable(self):
        self.assertFalse(pitchmap.on_pitch([(0, 40.0)], margin=2.0)[0])
