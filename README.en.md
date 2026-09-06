# football-setpiece-spotter

Finds set-piece candidates — corners first — in fixed wide-angle amateur
football footage, and measures how many it misses.

**Status: one half measured.** On the second half of one university match — 48
minutes, five corners — the spotter finds **all five**, produces **six**
candidates, and is a **median one second** off the restart. Reviewing its output
takes 3 minutes against 48 minutes of match. Five corners is one half of one
match and generalises to nothing; the numbers are in
[docs/RESULTS.md](docs/RESULTS.md) with what they do and do not support.

These candidates come from the dataset's ground-truth player positions, not from
this project's own perception. Measuring what is lost when the positions come
from a detector instead is the next step, and it is the number that decides
whether any of this works on footage nobody has annotated.

## Why another football-video repository

Detection → tracking → team clustering → homography → possession is a solved
recipe, published as a library by Roboflow and rebuilt in a long tail of public
repositories. Rebuilding it again is not the point here.

The question this tool answers is the one an amateur club's analyst actually
has:

> Given 90 minutes of footage from the camera on the touchline, how many
> minutes must a human still watch to find every corner, and how many corners
> does the tool miss?

So the headline numbers are **recall, candidate count and review time**, not a
demo video with boxes drawn on it. Ground truth is labelled before the detector
is written, and a detector change that ships without an evaluation run is a
change that has not been shown to help.

## What works today

```console
$ setpiece info data/raw/match.mp4
file:       data/raw/match.mp4
resolution: 3840x2160  (8.3 MP)
codec:      hevc
frame rate: 29.970 fps
duration:   01:30:00  (5400.0s)
frames:     161,838

coarse pass at 2 fps: 10,800 frames (6.7% of the file)
coarse pass at 4 fps: 21,600 frames (13.3% of the file)
```

```console
$ setpiece template > data/labels/match.csv   # then label the match by hand
$ setpiece evaluate data/labels/match.csv data/output/candidates.csv --video data/raw/match.mp4
event:      all
tolerance:  +/-15s
labelled:   14
candidates: 22
...
```

- `setpiece info` — what a file actually is, and what a coarse pass over it
  would cost. Handles the containers consumer cameras write: absent frame
  counts, absent stream durations, variable frame rates.
- `setpiece template` — an empty ground-truth file with the accepted
  vocabulary.
- `setpiece evaluate` — scores candidates against ground truth: recall,
  precision, median timing offset, the list of what was missed, and the review
  time the candidate list implies.
- `setpiece import-gsr` — streams a 2.7 GB SoccerTrack v2 game-state file and
  writes the 1.6 million player positions inside it as a 4.4 MB gzipped CSV.
- `setpiece corners` — finds corner candidates in those positions. The ball is
  not used: the released ball track is live for a third of the frames and is
  clamped to the pitch corner when it is not, which puts a phantom ball exactly
  where a corner detector wants to see one.

Everything above runs on the standard library plus `ffprobe`. No model, no GPU,
no network.

## What does not exist yet

The detector, the tracker and the team classifier — measured by
`setpiece evaluate` against the same ground truth, so that the cost of
perception is a number rather than an excuse. See [docs/DECISIONS.md](docs/DECISIONS.md) for what
has already been decided and why, including why the default detector is
RF-DETR (Apache-2.0) rather than an AGPL-licensed YOLO.

Footage is settled: **SoccerTrack v2** (10 university matches, ~900 minutes,
fixed BePro panoramic 4K, CC BY 4.0) is the development and evaluation set, with
Simula's Alfheim panoramas as a professional-football contrast. Corner is not
one of its 12 annotated action classes, so the corner ground truth is still
written by hand — see [docs/FOOTAGE.md](docs/FOOTAGE.md) and
[docs/LABELLING.md](docs/LABELLING.md).

## Install

```bash
python -m pip install .        # measurement layer only
python -m pip install '.[detect]'   # adds the model runtime, once it exists
```

Requires Python 3.9+ and FFmpeg (`brew install ffmpeg`).

## Data

No footage, frames, labels or model weights are in this repository, and CI
fails if any are committed. See [docs/DATA_POLICY.md](docs/DATA_POLICY.md).

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

No network, no GPU, no video file required.

## Licence

MIT. See [LICENSE](LICENSE).
