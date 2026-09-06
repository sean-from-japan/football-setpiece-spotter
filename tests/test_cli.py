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
