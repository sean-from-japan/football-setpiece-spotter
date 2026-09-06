import io
import unittest

from setpiece import labels


class LoadTest(unittest.TestCase):
    def test_reads_a_hand_written_file(self):
        events = labels.loads(
            "time,event,team,note\n"
            "12:31,corner,home,short corner\n"
            "00:24:42,corner,away,\n"
        )
        self.assertEqual([item.time for item in events], [751.0, 1482.0])
        self.assertEqual(events[0].note, "short corner")

    def test_sorts_by_time_so_a_late_addition_is_harmless(self):
        events = labels.loads("time,event\n30:00,corner\n02:00,throw_in\n")
        self.assertEqual([item.event for item in events], ["throw_in", "corner"])

    def test_tolerates_a_byte_order_mark_and_spreadsheet_padding(self):
        events = labels.loads("﻿Time , Event \n 12:31 , Corner \n\n")
        self.assertEqual(events[0].event, "corner")

    def test_names_the_offending_line(self):
        with self.assertRaises(labels.LabelError) as caught:
            labels.loads("time,event\n12:31,corner\n13:00,tackle\n")
        self.assertIn("line 3", str(caught.exception))

    def test_rejects_a_file_with_no_header(self):
        for text in ("", "12:31,corner\n"):
            with self.assertRaises(labels.LabelError):
                labels.loads(text)

    def test_confidence_is_bounded(self):
        with self.assertRaises(labels.LabelError):
            labels.loads("time,event,confidence\n12:31,corner,1.4\n")


class DumpTest(unittest.TestCase):
    def test_round_trips_through_the_reader(self):
        original = labels.loads("time,event,team,confidence\n12:31,corner,home,0.84\n")
        buffer = io.StringIO()
        labels.dump(original, buffer)
        again = labels.loads(buffer.getvalue())
        self.assertEqual(again[0].time, original[0].time)
        self.assertEqual(again[0].confidence, 0.84)
