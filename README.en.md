# football-setpiece-spotter

Finds set-piece candidates — corners first — in fixed wide-angle amateur
football footage, and measures how many it misses.

**Status: it works on the dataset's tracking and does not survive our own.**

Across two halves of two university matches — 96 minutes, twelve corners — the
spotter finds **all twelve** from the dataset's ground-truth player positions,
at a precision of 0.83 and 1.00, timed within a second of the restart.

Run on positions produced here instead — RF-DETR tiled over the panorama,
mapped to the pitch — it reaches 1.00 recall on the half its settings were
chosen on and **0.43 recall, 0.25 precision** on a half it had not seen. The
crowd in the penalty area survives perception; the lone player standing on the
corner flag does not, and the heuristic leans its whole weight on that one
person.

The numbers, the failure measured corner by corner, and what the design should
change are in [docs/RESULTS.md](docs/RESULTS.md).

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

Two more commands produce positions instead of consuming them, and these are
the ones that need the `detect` extra:

- `setpiece detect` — runs RF-DETR over the panorama in tiles and caches one
  row per person per sampled frame. The tile grid is an argument because it
  changes what the detector can see at all, not how fast it runs
  ([docs/DECISIONS.md](docs/DECISIONS.md), D7).
- `setpiece map-detections` — turns those boxes in pixels into positions in
  metres, fitting the mapping against known positions and refusing the
  positions the fit invents off the pitch.

`setpiece detect | map-detections | corners | evaluate` is the whole pipeline,
and it is what produced the perception numbers above.

## What does not exist yet

The tracker and the team classifier. Detections are matched to nothing between
frames, so the spotter sees a crowd rather than the same twenty-two people
moving — which is enough for counting bodies in a penalty area and not enough
for anything that needs identity.

Neither will ship without a `setpiece evaluate` run against the same ground
truth, so that the cost of perception stays a number rather than an excuse. See
[docs/DECISIONS.md](docs/DECISIONS.md) for what has already been decided and
why, including why the default detector is RF-DETR (Apache-2.0) rather than an
AGPL-licensed YOLO.

Footage is settled: **SoccerTrack v2** (10 university matches, ~900 minutes,
fixed BePro panoramic 4K, CC BY 4.0) is the development and evaluation set, with
Simula's Alfheim panoramas as a professional-football contrast. Corner is not
one of its 12 annotated action classes, so the corner ground truth is still
written by hand — see [docs/FOOTAGE.md](docs/FOOTAGE.md) and
[docs/LABELLING.md](docs/LABELLING.md).

## Install

```bash
python -m pip install .              # measurement layer only
python -m pip install '.[detect]'    # adds the detector and the pitch mapping
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
