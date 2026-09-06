"""Finding corner-kick candidates from player positions alone.

The ball is not used. On this dataset the provided ball track is live for only
about a third of the frames and is clamped to the pitch rectangle when it is
not, which puts a phantom ball on the corner flag exactly where a corner
detector wants to see one. Players, by contrast, are tracked continuously.

The shape being looked for is the one an analyst recognises instantly: almost
everybody inside one penalty area, and one player standing on the corner arc.
"""

import math
from dataclasses import dataclass

from .labels import Event

#: Pitch half-dimensions in metres, matching SoccerTrack v2's convention of a
#: 105 x 68 m pitch with the origin on the centre spot.
HALF_LENGTH = 52.5
HALF_WIDTH = 34.0

#: The penalty area: 16.5 m deep, 40.32 m wide.
BOX_DEPTH = 16.5
BOX_HALF_WIDTH = 20.16


@dataclass(frozen=True)
class Settings:
    """Everything the heuristic can be argued about, in one place."""

    corner_radius: float = 3.0      # how close a player must be to the flag
    min_in_box: int = 10            # people inside the penalty area
    scan_fps: float = 5.0           # positions are examined this often
    merge_gap: float = 20.0         # seconds of interruption still one situation
    min_duration: float = 0.0       # seconds a situation must last

    def __post_init__(self):
        for name in ("corner_radius", "scan_fps", "merge_gap"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.min_in_box < 1:
            raise ValueError("min_in_box must be at least 1")


CORNERS = (
    (HALF_LENGTH, HALF_WIDTH),
    (HALF_LENGTH, -HALF_WIDTH),
    (-HALF_LENGTH, HALF_WIDTH),
    (-HALF_LENGTH, -HALF_WIDTH),
)


def _corner_shape(people, settings):
    """Return the corner this frame looks like, or ``None``.

    ``people`` is a sequence of ``(track, team, role, x, y)``.
    """
    best = None
    for corner_x, corner_y in CORNERS:
        if not any(math.hypot(x - corner_x, y - corner_y) <= settings.corner_radius
                   for _, _, _, x, y in people):
            continue
        # Count everybody in the penalty area at that end. Attackers and
        # defenders both belong in the count: what identifies a corner is that
        # the whole game has moved into one box, not which side is in it.
        in_box = sum(
            1 for _, _, _, x, y in people
            if (x >= HALF_LENGTH - BOX_DEPTH if corner_x > 0 else x <= -HALF_LENGTH + BOX_DEPTH)
            and abs(y) <= BOX_HALF_WIDTH
        )
        if in_box >= settings.min_in_box and (best is None or in_box > best[1]):
            best = ((corner_x, corner_y), in_box)
    return best


@dataclass
class Situation:
    """A stretch of frames that looked like one corner."""

    corner: tuple
    start: float
    end: float
    crowd: int
    frames: int

    @property
    def duration(self):
        return self.end - self.start


def situations(frames, fps, settings=None):
    """Group the frames whose geometry looks like a corner into situations."""
    settings = settings or Settings()
    step = max(1, int(round(fps / settings.scan_fps)))
    found = []
    current = None

    for frame in range(min(frames or [1]), max(frames or [1]) + 1, step):
        people = frames.get(frame)
        if not people:
            continue
        shape = _corner_shape(people, settings)
        moment = frame / fps
        if shape is None:
            continue
        corner, crowd = shape
        if current and current.corner == corner and moment - current.end <= settings.merge_gap:
            current.end = moment
            current.crowd = max(current.crowd, crowd)
            current.frames += 1
        else:
            if current:
                found.append(current)
            current = Situation(corner=corner, start=moment, end=moment,
                                crowd=crowd, frames=1)
    if current:
        found.append(current)
    return [s for s in found if s.duration >= settings.min_duration]


def _confidence(situation, settings):
    """A number for ranking candidates, not a probability.

    Two things separate a corner from a passing resemblance to one: how long the
    shape held, and how many people were in the box. Both saturate — a corner
    that took a minute to take is not more of a corner than one that took
    twenty seconds.
    """
    held = min(situation.duration / 10.0, 1.0)
    crowded = min((situation.crowd - settings.min_in_box) / 8.0, 1.0)
    return round(0.4 + 0.4 * held + 0.2 * crowded, 2)


def candidates(frames, fps, settings=None, team_of=None):
    """Return corner candidates as :class:`~setpiece.labels.Event` objects.

    A situation is timed at its **end**, not its middle: the shape dissolves
    when the kick is taken, so the last frame that still looks like a corner is
    the closest thing in the geometry to the restart itself. Timing it at the
    midpoint would put every candidate ten to twenty seconds early, back in the
    walk-up, which is a systematic error that
    :attr:`setpiece.evaluate.Result.median_offset` is meant to expose.
    """
    settings = settings or Settings()
    events = []
    for situation in situations(frames, fps, settings):
        events.append(Event(
            time=situation.end,
            event="corner",
            team=team_of(situation) if team_of else "",
            confidence=_confidence(situation, settings),
            note=f"{situation.duration:.0f}s at ({situation.corner[0]:+.0f},"
                 f"{situation.corner[1]:+.0f}), {situation.crowd} in the box",
        ))
    return events
