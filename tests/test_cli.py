import contextlib
import io
import os
import shutil
import tempfile
import unittest

from setpiece import cli

LABELS = "time,event,team\n10:00,corner,home\n20:00,corner,away\n"
CANDIDATES = "time,event,team,confidence\n10:04,corner,home,0.8\n41:00,corner,away,0.3\n"


@contextlib.contextmanager
def files(**contents):
    with tempfile.TemporaryDirectory() as folder:
        paths = {}
        for name, text in contents.items():
            path = os.path.join(folder, f"{name}.csv")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            paths[name] = path
        yield paths


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = cli.main(list(argv))
    return status, out.getvalue(), err.getvalue()


class EvaluateCommandTest(unittest.TestCase):
    def test_scores_two_files(self):
        with files(truth=LABELS, found=CANDIDATES) as paths:
            status, out, _ = run("evaluate", paths["truth"], paths["found"],
                                 "--duration", "90:00")
            self.assertEqual(status, 0)
            self.assertIn("recall:     0.50", out)
            self.assertIn("review:", out)

    def test_fail_under_turns_a_bad_run_into_a_non_zero_exit(self):
        with files(truth=LABELS, found=CANDIDATES) as paths:
            status, _, err = run("evaluate", paths["truth"], paths["found"],
                                 "--fail-under", "0.9")
            self.assertEqual(status, 1)
            self.assertIn("below", err)

    def test_a_broken_label_file_is_an_error_not_a_traceback(self):
        with files(truth="time,event\n10:00,tackle\n", found=CANDIDATES) as paths:
            status, _, err = run("evaluate", paths["truth"], paths["found"])
            self.assertEqual(status, 2)
            self.assertIn("setpiece:", err)

    @unittest.skipIf(shutil.which("ffprobe") is None, "ffprobe is not installed")
    def test_a_missing_video_is_reported_by_name(self):
        with files(truth=LABELS, found=CANDIDATES) as paths:
            status, _, err = run("evaluate", paths["truth"], paths["found"],
                                 "--video", "/no/such/match.mp4")
            self.assertEqual(status, 2)
            self.assertIn("match.mp4", err)


class TemplateCommandTest(unittest.TestCase):
    def test_the_template_is_readable_by_the_evaluator(self):
        from setpiece import labels

        _, out, err = run("template")
        events = labels.loads(out)
        self.assertEqual(events[0].event, "corner")
        self.assertIn("corner", err)  # the vocabulary is printed as a comment


class ParserTest(unittest.TestCase):
    def test_a_command_is_required(self):
        with self.assertRaises(SystemExit):
            run()

    def test_version_is_reported(self):
        with self.assertRaises(SystemExit):
            run("--version")


class GameStateCommandsTest(unittest.TestCase):
    def test_import_then_spot_corners(self):
        import gzip
        import json

        from setpiece import labels

        def person(image_id, track, x, y):
            return {"id": f"{image_id}{track}", "image_id": image_id, "track_id": track,
                    "supercategory": "object",
                    "attributes": {"role": "player", "team": "left", "jersey": "1"},
                    "bbox_pitch": {"x_bottom_middle": x, "y_bottom_middle": y}}

        records = []
        for frame in range(1, 400):
            image_id = f"3{frame:06d}"
            shaped = 100 <= frame < 300
            records.append(person(image_id, 99, 52.4 if shaped else 0.0, -34.0 if shaped else 0.0))
            for n in range(12):
                records.append(person(image_id, n, 44.0 if shaped else 0.0, -10.0 + n))

        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "half.json")
            with open(source, "w", encoding="utf-8") as handle:
                json.dump({"info": {"frame_rate": 25}, "images": [], "annotations": records}, handle)
            cache = os.path.join(folder, "positions.csv.gz")

            status, out, _ = run("import-gsr", source, cache)
            self.assertEqual(status, 0)
            self.assertIn("player positions", out)
            with gzip.open(cache, "rt", encoding="utf-8") as handle:
                self.assertTrue(handle.readline().startswith("frame,"))

            status, out, _ = run("corners", cache, "--fps", "25")
            self.assertEqual(status, 0)
            found = labels.loads(out)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].event, "corner")

    def test_a_position_cache_that_is_not_one_is_an_error(self):
        with files(truth=LABELS) as paths:
            status, _, err = run("corners", paths["truth"])
            self.assertEqual(status, 2)
            self.assertIn("setpiece:", err)


try:
    import numpy  # noqa: F401
    import scipy  # noqa: F401
    HAS_FIT = True
except ImportError:  # pragma: no cover
    HAS_FIT = False


@unittest.skipUnless(HAS_FIT, "numpy and scipy are needed to fit the mapping")
class MapDetectionsTest(unittest.TestCase):
    """Detections in pixels become positions in metres, with no correspondence given."""

    @staticmethod
    def to_pitch(x, y):
        u, v = x / 4096 * 2 - 1, y / 1080 * 2 - 1
        return 52.5 * u + 5.0 * u * v, 34.0 * v

    def test_places_detections_on_the_pitch(self):
        import csv
        import gzip
        import random

        from setpiece import detect, soccertrack

        rng = random.Random(11)
        with tempfile.TemporaryDirectory() as folder:
            detections = os.path.join(folder, "boxes.csv")
            reference = os.path.join(folder, "reference.csv.gz")
            with open(detections, "w", newline="", encoding="utf-8") as box_file, \
                    gzip.open(reference, "wt", newline="", encoding="utf-8") as ref_file:
                boxes = csv.writer(box_file)
                boxes.writerow(detect.COLUMNS)
                positions = csv.writer(ref_file)
                positions.writerow(soccertrack.COLUMNS)
                for frame in range(1, 61):
                    for _ in range(20):
                        x = rng.uniform(300, 3800)
                        y = rng.uniform(300, 900)
                        boxes.writerow([frame, round(x - 10, 1), round(y - 40, 1),
                                        round(x + 10, 1), round(y, 1), 0.9])
                        px, py = self.to_pitch(x, y)
                        positions.writerow([frame, 1, "left", "player",
                                            round(px, 3), round(py, 3)])

            out = os.path.join(folder, "mapped.csv.gz")
            status, printed, err = run("map-detections", detections, reference, out,
                                       "--fit-frames", "30")
            self.assertEqual(status, 0)
            self.assertIn("RMSE", err)
            self.assertIn("positions ->", printed)

            mapped = soccertrack.load_positions(out)
            self.assertEqual(len(mapped), 60)
            xs = [row[3] for rows in mapped.values() for row in rows]
            self.assertGreater(max(xs), 30)
            self.assertLess(min(xs), -30)

    def test_detections_and_reference_that_share_no_frame_are_refused(self):
        import csv
        import gzip

        from setpiece import detect, soccertrack

        with tempfile.TemporaryDirectory() as folder:
            detections = os.path.join(folder, "boxes.csv")
            with open(detections, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(detect.COLUMNS)
                writer.writerow([1, 0, 0, 10, 10, 0.9])
            reference = os.path.join(folder, "reference.csv.gz")
            with gzip.open(reference, "wt", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(soccertrack.COLUMNS)
                writer.writerow([99, 1, "left", "player", 0.0, 0.0])
            status, _, err = run("map-detections", detections, reference,
                                 os.path.join(folder, "out.csv.gz"))
            self.assertEqual(status, 2)
            self.assertIn("no frame appears in both", err)
