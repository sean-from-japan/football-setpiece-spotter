"""Scoring candidate set pieces against hand-labelled ground truth.

This module is the point of the project. A spotter that draws boxes on a video
proves nothing; a spotter that says "22 candidates, 11 minutes of review, one
corner missed out of fourteen" answers the question an analyst has.
"""

from dataclasses import dataclass, field

from . import timecode


@dataclass(frozen=True)
class Match:
    """A candidate paired with the label it is taken to have found."""

    label: object
    candidate: object

    @property
    def offset(self):
        """Signed seconds by which the candidate is late."""
        return self.candidate.time - self.label.time


@dataclass
class Result:
    """The outcome of scoring one candidate list against one label list."""

    event: str
    tolerance: float
    matches: list = field(default_factory=list)
    missed: list = field(default_factory=list)
    spurious: list = field(default_factory=list)
    duration: float = 0.0
    clip_seconds: float = 30.0

    @property
    def true_positives(self):
        return len(self.matches)

    @property
    def precision(self):
        found = len(self.matches) + len(self.spurious)
        return len(self.matches) / found if found else 0.0

    @property
    def recall(self):
        actual = len(self.matches) + len(self.missed)
        return len(self.matches) / actual if actual else 0.0

    @property
    def f1(self):
        precision, recall = self.precision, self.recall
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @property
    def median_offset(self):
        """Median signed offset of the matched candidates, in seconds.

        A systematic offset is a fixable bug — the detector is firing on the
        stoppage rather than on the restart — while a scattered one is noise.
        The mean would hide the difference behind one bad match.
        """
        if not self.matches:
            return 0.0
        offsets = sorted(match.offset for match in self.matches)
        middle = len(offsets) // 2
        if len(offsets) % 2:
            return offsets[middle]
        return (offsets[middle - 1] + offsets[middle]) / 2

    @property
    def review_seconds(self):
        """How long a human spends watching the candidate clips."""
        return (len(self.matches) + len(self.spurious)) * self.clip_seconds

    @property
    def review_fraction(self):
        """Review time as a fraction of watching the match itself."""
        if self.duration <= 0:
            return 0.0
        return self.review_seconds / self.duration


def score(labels, candidates, tolerance=15.0, event=None, require_team=False,
          min_confidence=0.0, duration=0.0, clip_seconds=30.0):
    """Match ``candidates`` to ``labels`` and return a :class:`Result`.

    Matching is greedy over the smallest time difference first, which is both
    the standard practice for action spotting and the only rule that behaves
    sensibly when a burst of candidates surrounds one real corner: the closest
    one is credited and the rest are counted as false positives, rather than the
    first one in file order taking the credit.

    ``tolerance`` is generous on purpose. The output is a clip for a human to
    open, so a candidate 10 seconds early still lands on the right restart; a
    tolerance tighter than the clip length would score the tool on something the
    reviewer never notices.
    """
    if tolerance <= 0:
        raise ValueError(f"tolerance must be positive, not {tolerance}")

    wanted = list(labels)
    found = [item for item in candidates if item.confidence >= min_confidence]
    if event:
        wanted = [item for item in wanted if item.event == event]
        found = [item for item in found if item.event == event]

    pairs = []
    for label in wanted:
        for candidate in found:
            if candidate.event != label.event:
                continue
            if require_team and label.team and candidate.team and candidate.team != label.team:
                continue
            distance = abs(candidate.time - label.time)
            if distance <= tolerance:
                pairs.append((distance, label, candidate))
    pairs.sort(key=lambda pair: (pair[0], pair[1].time, pair[2].time))

    matched_labels, matched_candidates, matches = set(), set(), []
    for _, label, candidate in pairs:
        if id(label) in matched_labels or id(candidate) in matched_candidates:
            continue
        matched_labels.add(id(label))
        matched_candidates.add(id(candidate))
        matches.append(Match(label=label, candidate=candidate))

    matches.sort(key=lambda match: match.label.time)
    return Result(
        event=event or "all",
        tolerance=tolerance,
        matches=matches,
        missed=[item for item in wanted if id(item) not in matched_labels],
        spurious=[item for item in found if id(item) not in matched_candidates],
        duration=duration,
        clip_seconds=clip_seconds,
    )


def report(result):
    """Return the human-readable summary printed by ``setpiece evaluate``."""
    lines = [
        f"event:      {result.event}",
        f"tolerance:  +/-{result.tolerance:g}s",
        f"labelled:   {len(result.matches) + len(result.missed)}",
        f"candidates: {len(result.matches) + len(result.spurious)}",
        "",
        f"recall:     {result.recall:.2f}  ({result.true_positives} found, {len(result.missed)} missed)",
        f"precision:  {result.precision:.2f}  ({len(result.spurious)} spurious)",
        f"f1:         {result.f1:.2f}",
        f"offset:     {result.median_offset:+.1f}s median",
    ]
    if result.duration > 0:
        lines.append(
            f"review:     {result.review_seconds / 60:.0f} min of clips vs "
            f"{result.duration / 60:.0f} min of match "
            f"({result.review_fraction:.0%})"
        )
    if result.missed:
        lines.append("")
        lines.append("missed:")
        for item in result.missed:
            note = f"  {item.note}" if item.note else ""
            lines.append(f"  {timecode.format(item.time)}  {item.event} {item.team}{note}")
    return "\n".join(lines)
