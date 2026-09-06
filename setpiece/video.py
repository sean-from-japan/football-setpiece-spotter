"""Reading what a video file actually is, before anything is inferred from it.

Match footage from consumer cameras is not the tidy input that tutorials
assume. The container may not know its own frame count, the stream may not know
its own duration, and a long recording is frequently not one file at all. All of
that is handled here so that no later stage has to guess.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass


class VideoError(RuntimeError):
    """ffprobe was unusable, or the file was not readable video."""


@dataclass(frozen=True)
class VideoInfo:
    """What is known about one video file."""

    path: str
    width: int
    height: int
    fps: float
    duration: float
    codec: str
    frame_count: int
    frame_count_is_estimated: bool

    @property
    def megapixels(self):
        return self.width * self.height / 1_000_000


def _rational(text):
    """Return a float from ffprobe's ``30000/1001`` style rates.

    ffprobe reports ``0/0`` for streams whose rate it cannot determine, which is
    not an error and must not raise: the caller decides what to do without a
    frame rate.
    """
    if not text:
        return None
    if "/" in str(text):
        numerator, _, denominator = str(text).partition("/")
        try:
            numerator, denominator = float(numerator), float(denominator)
        except ValueError:
            return None
        if denominator == 0:
            return None
        return numerator / denominator
    try:
        return float(text)
    except ValueError:
        return None


def _first_video_stream(payload):
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    return None


def parse_probe(payload, path="<memory>"):
    """Turn a parsed ``ffprobe -show_format -show_streams -of json`` payload into
    a :class:`VideoInfo`.

    Kept separate from running ffprobe so the awkward cases can be tested
    without a video file: this is where the fallbacks live.
    """
    stream = _first_video_stream(payload)
    if stream is None:
        raise VideoError(f"no video stream in {path}")

    try:
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, TypeError, ValueError):
        raise VideoError(f"no frame size reported for {path}")

    # `avg_frame_rate` is the average over the whole file and `r_frame_rate` the
    # nominal base rate. For variable-frame-rate action-camera footage they
    # differ, and the average is the one that converts a timestamp to a frame
    # index correctly.
    fps = _rational(stream.get("avg_frame_rate")) or _rational(stream.get("r_frame_rate"))
    if not fps:
        raise VideoError(f"no usable frame rate for {path}")

    duration = None
    for source in (stream.get("duration"), payload.get("format", {}).get("duration")):
        try:
            duration = float(source)
        except (TypeError, ValueError):
            continue
        if duration > 0:
            break
        duration = None
    if duration is None:
        raise VideoError(f"no duration reported for {path}")

    # `nb_frames` is absent from most MP4 files written by cameras. Estimating
    # it from duration is close enough for planning work, but downstream code
    # has to be able to tell the difference, so the flag travels with the value.
    estimated = False
    try:
        frame_count = int(stream["nb_frames"])
        if frame_count <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        frame_count = int(round(duration * fps))
        estimated = True

    return VideoInfo(
        path=str(path),
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        codec=stream.get("codec_name", "unknown"),
        frame_count=frame_count,
        frame_count_is_estimated=estimated,
    )


def probe(path, ffprobe="ffprobe"):
    """Run ffprobe on ``path`` and return a :class:`VideoInfo`."""
    if shutil.which(ffprobe) is None:
        raise VideoError(
            f"{ffprobe} was not found on PATH; install FFmpeg (macOS: brew install ffmpeg)"
        )
    command = [
        ffprobe,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"exit status {completed.returncode}"
        raise VideoError(f"ffprobe failed on {path}: {message}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise VideoError(f"ffprobe returned unreadable JSON for {path}: {error}")
    return parse_probe(payload, path)


def frame_index(info, seconds):
    """Return the frame index nearest ``seconds``, clamped to the file."""
    if seconds < 0:
        raise ValueError(f"negative timestamp: {seconds}")
    index = int(round(seconds * info.fps))
    return min(index, max(info.frame_count - 1, 0))


def frame_time(info, index):
    """Return the timestamp of frame ``index``."""
    if index < 0:
        raise ValueError(f"negative frame index: {index}")
    return index / info.fps


def sample_times(info, sample_fps, start=0.0, end=None):
    """Return the timestamps of a coarse pass over ``[start, end)``.

    Sampling every frame of a match is the single easiest way to make this
    project impossible on a laptop: 90 minutes at 30 fps is 162,000 frames,
    while 4 fps is 21,600. Set pieces last seconds, so the coarse pass is not a
    compromise on the events being looked for.
    """
    if sample_fps <= 0:
        raise ValueError(f"sample_fps must be positive, not {sample_fps}")
    if end is None or end > info.duration:
        end = info.duration
    if start < 0:
        raise ValueError(f"negative start: {start}")
    if end <= start:
        return []

    step = 1.0 / sample_fps
    times = []
    # Counting in integers rather than adding `step` repeatedly keeps the last
    # sample of a 90-minute pass from drifting by several frames.
    count = 0
    while True:
        moment = start + count * step
        if moment >= end:
            break
        times.append(moment)
        count += 1
    return times
