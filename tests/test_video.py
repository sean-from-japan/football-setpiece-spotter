import unittest

from setpiece import video


def payload(**stream):
    base = {
        "codec_type": "video",
        "codec_name": "hevc",
        "width": 3840,
        "height": 2160,
        "avg_frame_rate": "30000/1001",
        "duration": "5400.0",
        "nb_frames": "161838",
    }
    base.update(stream)
    return {"streams": [{"codec_type": "audio"}, base], "format": {"duration": "5400.0"}}


class ParseProbeTest(unittest.TestCase):
    def test_reads_a_well_formed_file(self):
        info = video.parse_probe(payload())
        self.assertAlmostEqual(info.fps, 29.97, places=2)
        self.assertEqual(info.frame_count, 161838)
        self.assertFalse(info.frame_count_is_estimated)
        self.assertAlmostEqual(info.megapixels, 8.29, places=2)

    def test_estimates_the_frame_count_when_the_container_omits_it(self):
        info = video.parse_probe(payload(nb_frames=None))
        self.assertTrue(info.frame_count_is_estimated)
        self.assertEqual(info.frame_count, round(5400 * 30000 / 1001))

    def test_falls_back_to_the_container_duration(self):
        info = video.parse_probe(payload(duration=None))
        self.assertEqual(info.duration, 5400.0)

    def test_falls_back_to_the_nominal_rate_when_the_average_is_unknown(self):
        info = video.parse_probe(payload(avg_frame_rate="0/0", r_frame_rate="60/1"))
        self.assertEqual(info.fps, 60.0)

    def test_refuses_a_file_it_cannot_plan_against(self):
        for broken in (
            {"streams": [{"codec_type": "audio"}]},
            payload(avg_frame_rate="0/0", r_frame_rate="0/0"),
            payload(width=None),
        ):
            with self.assertRaises(video.VideoError):
                video.parse_probe(broken)

    def test_refuses_a_zero_duration_rather_than_reporting_an_empty_match(self):
        broken = payload(duration="0")
        broken["format"]["duration"] = "0"
        with self.assertRaises(video.VideoError):
            video.parse_probe(broken)


class SamplingTest(unittest.TestCase):
    def setUp(self):
        self.info = video.parse_probe(payload())

    def test_a_coarse_pass_is_a_small_fraction_of_the_frames(self):
        times = video.sample_times(self.info, 4)
        self.assertEqual(len(times), 21600)
        self.assertLess(len(times) / self.info.frame_count, 0.15)

    def test_the_last_sample_has_not_drifted(self):
        times = video.sample_times(self.info, 4)
        self.assertAlmostEqual(times[-1], 5399.75, places=6)

    def test_a_window_is_half_open(self):
        times = video.sample_times(self.info, 2, start=10, end=12)
        self.assertEqual(times, [10.0, 10.5, 11.0, 11.5])

    def test_an_empty_or_impossible_window_yields_nothing(self):
        self.assertEqual(video.sample_times(self.info, 2, start=30, end=30), [])
        with self.assertRaises(ValueError):
            video.sample_times(self.info, 0)

    def test_frame_index_is_clamped_to_the_file(self):
        self.assertEqual(video.frame_index(self.info, 0), 0)
        self.assertEqual(video.frame_index(self.info, 10_000), self.info.frame_count - 1)
        self.assertAlmostEqual(video.frame_time(self.info, 30), 30 / self.info.fps)
