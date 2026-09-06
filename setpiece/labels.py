"""Ground truth, and the candidate list that is scored against it.

Both live in CSV because both are read and edited by a human: the labels are
typed while watching a match, and the candidates are what the reviewer opens.
"""

import csv
import io
from dataclasses import dataclass

from . import timecode

#: Restart types a human can label reliably from wide footage without a
#: touch-by-touch view. Passes and duels are deliberately absent: a label nobody
#: can produce consistently makes the recall number meaningless rather than
#: strict.
EVENTS = (
    "corner",
    "throw_in",
    "free_kick",
    "goal_kick",
    "kick_off",
    "penalty",
    "goal",
)

TEAMS = ("home", "away", "team_a", "team_b")


class LabelError(ValueError):
    """A label or candidate file could not be read."""


@dataclass(frozen=True)
class Event:
    """One labelled or detected moment.

    ``time`` is the instant the restart is taken, not the stoppage before it.
    """

    time: float
    event: str
    team: str = ""
    confidence: float = 1.0
    note: str = ""
    source_line: int = 0


def _require(condition, line, message):
    if not condition:
        raise LabelError(f"line {line}: {message}")


def _read(handle, path, allow_confidence):
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
        raise LabelError(f"{path} is empty; it needs a header row")
    columns = {name.strip().lower() for name in reader.fieldnames if name}
    for required in ("time", "event"):
        if required not in columns:
            raise LabelError(f"{path} has no '{required}' column; got {sorted(columns)}")

    events = []
    for offset, row in enumerate(reader, start=2):
        row = {(key or "").strip().lower(): (value or "").strip()
               for key, value in row.items()}
        if not row.get("time") and not row.get("event"):
            continue  # a blank line left behind by a spreadsheet

        try:
            moment = timecode.parse(row.get("time", ""))
        except timecode.TimecodeError as error:
            raise LabelError(f"line {offset}: {error}")

        name = row.get("event", "").lower()
        _require(name in EVENTS, offset,
                 f"unknown event {name!r}; allowed: {', '.join(EVENTS)}")

        team = row.get("team", "").lower()
        _require(team == "" or team in TEAMS, offset,
                 f"unknown team {team!r}; allowed: {', '.join(TEAMS)}")

        confidence = 1.0
        if allow_confidence and row.get("confidence"):
            try:
                confidence = float(row["confidence"])
            except ValueError:
                raise LabelError(f"line {offset}: confidence is not a number")
            _require(0.0 <= confidence <= 1.0, offset,
                     f"confidence must be within 0..1, not {confidence}")

        events.append(Event(
            time=moment,
            event=name,
            team=team,
            confidence=confidence,
            note=row.get("note", ""),
            source_line=offset,
        ))

    events.sort(key=lambda item: item.time)
    return events


def load(path, allow_confidence=True):
    """Read a label or candidate CSV."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return _read(handle, path, allow_confidence)


def loads(text, path="<string>", allow_confidence=True):
    """Read the same format from a string.

    The byte-order mark is stripped here rather than by the codec, because a
    string that came from a spreadsheet export carries it just as a file does.
    """
    return _read(io.StringIO(text.lstrip("\ufeff")), path, allow_confidence)


def dump(events, handle, confidence=True):
    """Write events as CSV, in the format :func:`load` reads back."""
    columns = ["time", "event", "team"] + (["confidence"] if confidence else []) + ["note"]
    writer = csv.writer(handle)
    writer.writerow(columns)
    for item in events:
        row = [timecode.format(item.time), item.event, item.team]
        if confidence:
            row.append(f"{item.confidence:.2f}")
        row.append(item.note)
        writer.writerow(row)
