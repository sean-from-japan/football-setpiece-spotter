import gzip
import io
import json
import os
import tempfile
import unittest

from setpiece import soccertrack


def annotation(image_id, track, team, role, x, y, supercategory="object"):
    return {
        "id": f"{image_id}{track}",
        "image_id": str(image_id),
        "track_id": track,
        "supercategory": supercategory,
        "attributes": {"role": role, "jersey": "9", "team": team},
        "bbox_image": {"x": 1, "y": 2, "w": 3, "h": 4},
        "bbox_pitch": {"x_bottom_middle": x, "y_bottom_middle": y},
    }


def document(annotations):
    return json.dumps(
        {
            "info": {"frame_rate": 25, "seq_length": 2},
            "images": [{"image_id": "3000001", "file_name": "000001.jpg"}],
            "annotations": annotations,
            "categories": [{"id": 2, "name": "player"}],
        },
        indent=4,
    )


class StreamTest(unittest.TestCase):
    def test_reads_players_and_skips_pitch_lines(self):
        text = document([
            {"id": "3000001P", "image_id": "3000001", "supercategory": "pitch",
             "lines": {"Big rect. left top": [{"x": 0.1, "y": 0.2}]}},
            annotation("3000001", 1, "left", "goalkeeper", -51.45, -0.68),
            annotation("3000002", 1, "left", "goalkeeper", -51.40, -0.70),
        ])
        rows = list(soccertrack._stream_array(io.StringIO(text), "annotations"))
        self.assertEqual(len(rows), 3)

    def test_survives_an_object_split_across_read_chunks(self):
        text = document([annotation("3000001", n, "right", "player", n, -n)
                         for n in range(1, 40)])
        # A chunk size far below one object forces the refill path on every read.
        rows = list(soccertrack._stream_array(io.StringIO(text), "annotations", chunk_size=17))
        self.assertEqual(len(rows), 39)
        self.assertEqual(rows[-1]["track_id"], 39)

    def test_an_empty_array_yields_nothing(self):
        rows = list(soccertrack._stream_array(io.StringIO(document([])), "annotations"))
        self.assertEqual(rows, [])

    def test_a_missing_array_is_an_error(self):
        with self.assertRaises(soccertrack.AnnotationError):
            list(soccertrack._stream_array(io.StringIO('{"info": {}}'), "annotations"))


class PositionsTest(unittest.TestCase):
    def positions(self, annotations):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "half.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(document(annotations))
            return list(soccertrack.player_positions(path))

    def test_frame_number_comes_from_the_image_id(self):
        rows = self.positions([annotation("3000042", 7, "left", "player", 1.5, -2.5)])
        self.assertEqual(rows, [(42, 7, "left", "player", 1.5, -2.5)])

    def test_records_without_pitch_coordinates_are_dropped(self):
        broken = annotation("3000001", 1, "left", "player", 0, 0)
        broken["bbox_pitch"] = None
        missing = annotation("3000002", 1, "left", "player", 0, 0)
        del missing["bbox_pitch"]["y_bottom_middle"]
        self.assertEqual(self.positions([broken, missing]), [])


class CacheTest(unittest.TestCase):
    def test_round_trips_through_the_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "half.json")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(document([
                    annotation("3000001", 1, "left", "goalkeeper", -51.4, -0.7),
                    annotation("3000001", 2, "right", "player", 10.0, 5.0),
                    annotation("3000002", 1, "left", "goalkeeper", -51.3, -0.7),
                ]))
            cache = os.path.join(folder, "cache", "half.csv.gz")
            self.assertEqual(soccertrack.import_game_state(source, cache), 3)

            frames = soccertrack.load_positions(cache)
            self.assertEqual(sorted(frames), [1, 2])
            self.assertEqual(len(frames[1]), 2)
            self.assertEqual(frames[1][1], (2, "right", "player", 10.0, 5.0))

    def test_a_file_with_no_players_is_an_error_not_an_empty_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "half.json")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(document([]))
            with self.assertRaises(soccertrack.AnnotationError):
                soccertrack.import_game_state(source, os.path.join(folder, "c.csv.gz"))

    def test_a_foreign_csv_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "other.csv.gz")
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write("time,event\n10:00,corner\n")
            with self.assertRaises(soccertrack.AnnotationError):
                soccertrack.load_positions(path)


class CornerLabelTest(unittest.TestCase):
    FEED = (
        "event_time,event_period,team_id,event_types,player_name\n"
        "2699520,SECOND_HALF,31790,passSucceeded,Kickoff Taker\n"
        "3153120,SECOND_HALF,31790,cornerKick crossFailed,Corner Taker\n"
        "3252120,SECOND_HALF,31790,cornerKick,Corner Taker\n"
        "1820840,FIRST_HALF,31425,cornerKick,Someone Else\n"
    )

    def feed(self, text=None):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "118577_player_nodes.csv")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.FEED if text is None else text)
        return path

    def test_reads_one_period_and_shifts_to_period_time(self):
        events = soccertrack.corner_labels(self.feed(), "SECOND_HALF", 2_699_520)
        self.assertEqual([round(e.time) for e in events], [454, 553])
        self.assertEqual({e.event for e in events}, {"corner"})

    def test_the_other_period_is_a_different_list(self):
        events = soccertrack.corner_labels(self.feed(), "FIRST_HALF", 0)
        self.assertEqual([round(e.time) for e in events], [1821])

    def test_no_player_name_reaches_the_output(self):
        events = soccertrack.corner_labels(self.feed(), "SECOND_HALF", 2_699_520)
        text = " ".join(f"{e.note} {e.team}" for e in events)
        self.assertNotIn("Taker", text)

    def test_a_wrong_offset_is_refused_rather_than_producing_negative_times(self):
        with self.assertRaises(soccertrack.AnnotationError):
            soccertrack.corner_labels(self.feed(), "SECOND_HALF", 5_000_000)

    def test_an_unknown_period_is_refused(self):
        with self.assertRaises(soccertrack.AnnotationError):
            soccertrack.corner_labels(self.feed(), "EXTRA_TIME", 0)

    def test_a_substring_match_is_not_a_corner(self):
        # 'cornerKickWon' would be a different event; token matching, not `in`.
        path = self.feed("event_time,event_period,team_id,event_types\n"
                         "2700000,SECOND_HALF,1,cornerKickWon\n")
        self.assertEqual(soccertrack.corner_labels(path, "SECOND_HALF", 2_699_520), [])
