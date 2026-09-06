"""Reading the SoccerTrack v2 annotations without loading them into memory.

One half of game-state annotation is a 2.7 GB pretty-printed JSON file, most of
it pitch-line annotations repeated for every one of 72,751 frames. The player
positions inside it are about one per cent of that. This module streams the file
and writes the part this project needs to a gzipped CSV, which is small enough
to read repeatedly and plain enough to inspect by eye.
"""

import csv
import gzip
import json
import os

#: Field names of the cache written by :func:`import_game_state`.
COLUMNS = ("frame", "track", "team", "role", "x", "y")


class AnnotationError(ValueError):
    """The annotation file was not in the expected format."""


def _stream_array(handle, key, chunk_size=1 << 22):
    """Yield the objects of the top-level array named ``key``.

    ``json.load`` would need the whole document in memory at once. Instead the
    file is read in chunks and decoded one array element at a time with
    ``raw_decode``, which stops at the end of the first complete value it finds.
    """
    decoder = json.JSONDecoder()
    buffer = ""
    found = False

    # Step 1: read forward until the array opens. The needle includes the
    # bracket so that a key of the same name nested elsewhere cannot match.
    needle = f'"{key}"'
    while not found:
        chunk = handle.read(chunk_size)
        if not chunk:
            raise AnnotationError(f"no {key!r} array in the file")
        buffer += chunk
        at = buffer.find(needle)
        if at == -1:
            buffer = buffer[-len(needle):]  # a key can straddle a chunk boundary
            continue
        opening = buffer.find("[", at)
        if opening == -1:
            continue
        buffer = buffer[opening + 1:]
        found = True

    # Step 2: decode elements until the array closes.
    while True:
        buffer = buffer.lstrip(" \t\r\n,")
        if not buffer:
            chunk = handle.read(chunk_size)
            if not chunk:
                return
            buffer += chunk
            continue
        if buffer[0] == "]":
            return
        try:
            value, end = decoder.raw_decode(buffer)
        except ValueError:
            chunk = handle.read(chunk_size)
            if not chunk:
                raise AnnotationError(f"the {key!r} array ends mid-object")
            buffer += chunk
            continue
        yield value
        buffer = buffer[end:]


def player_positions(path):
    """Yield ``(frame, track, team, role, x, y)`` for every tracked person.

    ``frame`` is the trailing part of SoccerTrack's ``image_id``: the ids run
    ``3000001``, ``3000002`` and so on, where the leading digits identify the
    sequence and the rest is a 1-based frame number.

    Records without pitch coordinates are skipped rather than reported as being
    at the centre spot; an annotation the dataset could not place is not a
    player standing in the middle of the pitch.
    """
    with open(path, encoding="utf-8") as handle:
        for record in _stream_array(handle, "annotations"):
            if record.get("supercategory") != "object":
                continue
            pitch = record.get("bbox_pitch")
            if not pitch:
                continue
            x = pitch.get("x_bottom_middle")
            y = pitch.get("y_bottom_middle")
            if x is None or y is None:
                continue
            attributes = record.get("attributes") or {}
            image_id = str(record.get("image_id", ""))
            if not image_id.isdigit():
                continue
            yield (
                int(image_id[1:]),
                record.get("track_id", -1),
                attributes.get("team") or "",
                attributes.get("role") or "",
                round(float(x), 3),
                round(float(y), 3),
            )


def import_game_state(path, destination):
    """Write the player positions of one half to a gzipped CSV. Returns the count."""
    written = 0
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    with gzip.open(destination, "wt", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(COLUMNS)
        for row in player_positions(path):
            writer.writerow(row)
            written += 1
    if not written:
        raise AnnotationError(f"{path} contained no player positions")
    return written


def load_positions(path):
    """Read a cache written by :func:`import_game_state`, grouped by frame.

    Returns ``{frame: [(track, team, role, x, y), ...]}``. One half is roughly
    1.6 million rows, which is large but not awkward; the alternative is
    re-reading gigabytes of JSON for every experiment.
    """
    frames = {}
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader, None)
        except gzip.BadGzipFile:
            # Pointing the command at a plain CSV — a label file, most likely —
            # otherwise surfaces as a decompression error from inside gzip.
            raise AnnotationError(f"{path} is not gzipped; expected a cache from import-gsr")
        if header != list(COLUMNS):
            raise AnnotationError(f"{path} is not a position cache; header was {header}")
        for frame, track, team, role, x, y in reader:
            frames.setdefault(int(frame), []).append(
                (int(track), team, role, float(x), float(y))
            )
    return frames


#: Periods as they are named in the match event feed shipped under ``raw/``.
PERIODS = ("FIRST_HALF", "SECOND_HALF")


def corner_labels(path, period, offset_ms):
    """Read corner kicks out of the match event feed in ``raw/``.

    The feed is a commercial one: ``<match>_player_nodes.csv`` carries an event
    vocabulary of 401 tokens, of which ``cornerKick`` is one. It is produced by
    human annotators from the video and owes nothing to the player tracking,
    which is what makes it usable as ground truth for a detector built on
    player geometry.

    **Only the timestamp, period and team id are read.** The file also holds
    the players' real names, so nothing else may leave it — see
    ``docs/DATA_POLICY.md``.
    """
    if period not in PERIODS:
        raise AnnotationError(f"period must be one of {PERIODS}, not {period!r}")

    from .labels import Event

    events = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("event_period") != period:
                continue
            if "cornerKick" not in (row.get("event_types") or "").split():
                continue
            try:
                moment = (int(row["event_time"]) - offset_ms) / 1000
            except (KeyError, TypeError, ValueError):
                raise AnnotationError(f"{path} has an unreadable event_time")
            if moment < 0:
                raise AnnotationError(
                    f"{path}: a corner at {moment:.0f}s is before the period started; "
                    "check offset_ms")
            events.append(Event(time=moment, event="corner",
                                note=f"team {row.get('team_id', '')}"))
    events.sort(key=lambda item: item.time)
    return events
