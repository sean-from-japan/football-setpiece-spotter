import unittest

from setpiece import evaluate, labels


def events(*rows):
    text = "time,event,team,confidence\n" + "".join(
        f"{time},{event},{team},{confidence}\n" for time, event, team, confidence in rows
    )
    return labels.loads(text)


class ScoreTest(unittest.TestCase):
    def test_a_candidate_inside_the_tolerance_counts(self):
        truth = events(("10:00", "corner", "home", 1.0))
        found = events(("10:08", "corner", "home", 0.8))
        result = evaluate.score(truth, found, tolerance=15)
        self.assertEqual(result.recall, 1.0)
        self.assertEqual(result.precision, 1.0)
        self.assertAlmostEqual(result.matches[0].offset, 8.0)

    def test_a_burst_credits_the_closest_candidate_not_the_first(self):
        truth = events(("10:00", "corner", "", 1.0))
        found = events(("09:52", "corner", "", 0.9), ("10:01", "corner", "", 0.4))
        result = evaluate.score(truth, found, tolerance=15)
        self.assertEqual(result.true_positives, 1)
        self.assertAlmostEqual(result.matches[0].offset, 1.0)
        self.assertEqual(len(result.spurious), 1)

    def test_one_candidate_cannot_cover_two_labels(self):
        truth = events(("10:00", "corner", "", 1.0), ("10:10", "corner", "", 1.0))
        found = events(("10:05", "corner", "", 1.0))
        result = evaluate.score(truth, found, tolerance=15)
        self.assertEqual(result.true_positives, 1)
        self.assertEqual(len(result.missed), 1)
        self.assertEqual(result.recall, 0.5)

    def test_event_types_do_not_cross_match(self):
        truth = events(("10:00", "corner", "", 1.0))
        found = events(("10:01", "throw_in", "", 1.0))
        result = evaluate.score(truth, found, tolerance=15)
        self.assertEqual(result.true_positives, 0)
        self.assertEqual(result.f1, 0.0)

    def test_team_is_ignored_unless_it_is_demanded(self):
        truth = events(("10:00", "corner", "home", 1.0))
        found = events(("10:02", "corner", "away", 1.0))
        self.assertEqual(evaluate.score(truth, found).true_positives, 1)
        self.assertEqual(
            evaluate.score(truth, found, require_team=True).true_positives, 0)

    def test_a_confidence_floor_drops_candidates_before_matching(self):
        truth = events(("10:00", "corner", "", 1.0))
        found = events(("10:02", "corner", "", 0.3))
        result = evaluate.score(truth, found, min_confidence=0.5)
        self.assertEqual(result.true_positives, 0)
        self.assertEqual(result.spurious, [])

    def test_median_offset_exposes_a_systematic_lag(self):
        truth = events(("10:00", "corner", "", 1.0), ("20:00", "corner", "", 1.0),
                       ("30:00", "corner", "", 1.0))
        found = events(("10:09", "corner", "", 1.0), ("20:10", "corner", "", 1.0),
                       ("30:11", "corner", "", 1.0))
        result = evaluate.score(truth, found)
        self.assertAlmostEqual(result.median_offset, 10.0)

    def test_review_time_is_reported_against_the_match_length(self):
        truth = events(("10:00", "corner", "", 1.0))
        found = events(("10:02", "corner", "", 1.0), ("40:00", "corner", "", 1.0))
        result = evaluate.score(truth, found, duration=5400, clip_seconds=30)
        self.assertEqual(result.review_seconds, 60)
        self.assertAlmostEqual(result.review_fraction, 60 / 5400)

    def test_empty_inputs_do_not_divide_by_zero(self):
        result = evaluate.score([], [], duration=0)
        self.assertEqual((result.precision, result.recall, result.f1), (0.0, 0.0, 0.0))
        self.assertEqual(result.median_offset, 0.0)
        self.assertEqual(result.review_fraction, 0.0)

    def test_tolerance_must_be_positive(self):
        with self.assertRaises(ValueError):
            evaluate.score([], [], tolerance=0)


class ReportTest(unittest.TestCase):
    def test_lists_what_was_missed(self):
        truth = events(("10:00", "corner", "home", 1.0), ("20:00", "corner", "away", 1.0))
        found = events(("10:02", "corner", "home", 1.0))
        text = evaluate.report(evaluate.score(truth, found, duration=5400))
        self.assertIn("recall:     0.50", text)
        self.assertIn("00:20:00", text)
