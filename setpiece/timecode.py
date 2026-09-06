"""Parsing and formatting of the timestamps that appear in labels and output.

A single module because three different layers need the same rules and they must
not drift apart: hand-written ground-truth labels, candidate output, and clip
file names.
"""


class TimecodeError(ValueError):
    """A timestamp could not be read."""


def parse(text):
    """Return seconds as a float from ``SS``, ``MM:SS`` or ``HH:MM:SS``.

    Fractional seconds are allowed in the last field. Labels are typed by hand
    while watching a match, so ``12:31``, ``00:12:31`` and ``751`` all have to
    mean the same instant; refusing one of them would only produce label files
    that fail for reasons that have nothing to do with football.
    """
    if isinstance(text, (int, float)):
        seconds = float(text)
        if seconds < 0:
            raise TimecodeError(f"negative timestamp: {text}")
        return seconds

    raw = str(text).strip()
    if not raw:
        raise TimecodeError("empty timestamp")
    if raw.startswith("-"):
        raise TimecodeError(f"negative timestamp: {raw}")

    fields = raw.split(":")
    if len(fields) > 3:
        raise TimecodeError(f"too many ':' fields: {raw}")
    try:
        numbers = [float(field) for field in fields]
    except ValueError:
        raise TimecodeError(f"not a timestamp: {raw}")

    # Only the last field may be fractional, and only the first may exceed its
    # base: 90:00 is a legitimate way to write ninety minutes.
    for number in numbers[:-1]:
        if number != int(number):
            raise TimecodeError(f"only the last field may be fractional: {raw}")
    for number in numbers[1:]:
        if number >= 60:
            raise TimecodeError(f"minutes and seconds must be below 60: {raw}")

    seconds = 0.0
    for number in numbers:
        seconds = seconds * 60 + number
    return seconds


def format(seconds, milliseconds=False):
    """Return ``HH:MM:SS`` (or ``HH:MM:SS.mmm``) for a number of seconds.

    Both forms are derived from the same rounded millisecond count so that a
    clip named ``00-12-31`` cannot end up listed as ``00:12:30.999`` in the CSV
    beside it.
    """
    if seconds < 0:
        raise TimecodeError(f"negative timestamp: {seconds}")
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    text = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    if milliseconds:
        text += f".{millis:03d}"
    return text


def filename(seconds):
    """Return a timestamp safe to embed in a file name (``00-12-31``)."""
    return format(seconds).replace(":", "-")
