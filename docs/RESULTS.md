# Results

## One half, five corners

Match 118577, second half — 48:19 of fixed panoramic footage from a Japanese
university game. Corner ground truth comes from the commercial match event feed
shipped in the dataset's `raw/` folder (`cornerKick`, 5 in this half), which is
annotated by people from the video and owes nothing to the player tracking the
detector uses.

Detector: `setpiece corners`, player positions only, no ball, no video.

| | |
|---|---|
| Corners in the half | 5 |
| Candidates produced | 6 |
| **Recall at ±15 s** | **1.00** (5 found, 0 missed) |
| **Precision at ±15 s** | **0.83** (1 spurious) |
| Median timing offset | **+1.0 s** |
| Review load | 3 minutes of clips against 48 minutes of match — **6%** |

Reproduce:

```bash
setpiece import-gsr data/soccertrack-v2/gsr/118577/118577_2nd.json data/cache/118577_2nd.csv.gz
setpiece corners data/cache/118577_2nd.csv.gz --output data/cache/candidates.csv
setpiece evaluate data/cache/truth.csv data/cache/candidates.csv --video <the half>
```

**Five corners is not a result to generalise from.** It is one half of one match.
The numbers below are reported so that the next half can be compared against
them, not because they establish anything yet.

## Where the timing is, and is not, good

| Ground truth | Candidate | Offset |
|---|---|---|
| 07:33 | 07:34 | +1 s |
| 09:12 | 09:13 | +1 s |
| 30:06 | 29:54 | **−12 s** |
| 37:47 | 37:48 | +1 s |
| 43:58 | 44:05 | +7 s |

Three of five land within a second. The two that do not are the two where the
corner-shaped configuration was detected only briefly — one second and two
seconds, against twenty and thirty for the others. Tightening the tolerance
shows the cost directly:

| Tolerance | Recall | Precision |
|---|---|---|
| ±2 s | 0.60 | 0.50 |
| ±5 s | 0.60 | 0.50 |
| ±10 s | 0.80 | 0.67 |
| ±15 s | 1.00 | 0.83 |

Any recall figure from this project is meaningless without its tolerance
attached. At the ±15 s used here a candidate still opens a clip showing the
right restart, which is what the tool is for; at ±2 s it would be claiming a
precision of timing it does not have.

## The confidence score does not work

`_confidence()` combines how long the shape held with how many people were in
the box. Ranking candidates by it makes the tool worse:

| Confidence floor | Recall | Precision |
|---|---|---|
| ≥ 0.5 | 1.00 | 0.83 |
| ≥ 0.6 | 0.40 | 0.67 |
| ≥ 0.7 | 0.40 | 1.00 |

The single false positive scores 0.62, higher than three of the five real
corners (0.55, 0.56, 0.57). Duration is not evidence of a corner: it separates
corners that took a long time to take from corners that were taken quickly, and
those are equally corners.

Filtering by this score is therefore not recommended, and the formula should
either be replaced by something with evidence behind it or removed. It is left
in place, unused by default, because deleting it would also delete the record
that it was tried.

## The one false positive

A candidate at 37:24, 23 seconds before the real corner at 37:47, at the same
corner of the pitch: the players had already gathered in the box while the ball
was still in play. Both fall inside the same review clip, so a human reviewing
this output loses nothing — but as a count of candidates it is a genuine extra.

## What has not been measured

- **Anything from this project's own perception.** These candidates come from
  the dataset's ground-truth player positions. The loss from using detections
  produced here instead is the next thing to measure, and it is the number that
  decides whether the tool works on footage with no annotations — which is every
  real use.
- **More than one half.** Six more halves are available for development.
- **Other set pieces.** Only corners are implemented.
