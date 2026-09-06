import unittest

from setpiece import timecode


class ParseTest(unittest.TestCase):
    def test_accepts_the_three_shapes_a_human_types(self):
        for text in ("751", "12:31", "00:12:31"):
            self.assertEqual(timecode.parse(text), 751.0, text)

    def test_keeps_fractions_of_the_last_field(self):
        self.assertAlmostEqual(timecode.parse("00:00:12.5"), 12.5)

    def test_allows_ninety_minutes_in_the_leading_field(self):
        self.assertEqual(timecode.parse("90:00"), 5400.0)

    def test_rejects_out_of_range_and_malformed_input(self):
        for text in ("12:75", "1:2:3:4", "-5", "", "corner", "1.5:00"):
            with self.assertRaises(timecode.TimecodeError, msg=text):
                timecode.parse(text)


class FormatTest(unittest.TestCase):
    def test_round_trips(self):
        self.assertEqual(timecode.format(timecode.parse("01:02:03")), "01:02:03")

    def test_second_and_millisecond_forms_agree_on_the_carry(self):
        self.assertEqual(timecode.format(59.9996), "00:01:00")
        self.assertEqual(timecode.format(59.9996, milliseconds=True), "00:01:00.000")

    def test_file_names_carry_no_colons(self):
        self.assertEqual(timecode.filename(751), "00-12-31")
