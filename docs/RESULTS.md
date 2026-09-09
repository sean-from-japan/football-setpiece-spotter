[日本語](RESULTS.ja.md) | English

# Results

## Two halves, twelve corners

Ground truth is the `cornerKick` label in the commercial match event feed
shipped in the dataset's `raw/` folder. It is annotated by people from the
video and owes nothing to the player tracking the detector uses.

| Half | Corners | Candidates | Recall | Precision | Offset |
|---|---|---|---|---|---|
| 118577 2nd (48:19) | 5 | 6 | **1.00** | **0.83** | +1.0 s |
| 128058 2nd (48:20) | 7 | 7 | **1.00** | **1.00** | −0.9 s |

Both from the dataset's ground-truth player positions, at ±15 s, with the same
settings — the second half was run after the first was written, with nothing
adjusted. Reviewing the twelve candidates takes about 6 minutes against 96
minutes of football.

Twelve corners across two halves of two matches is a small number and the
tolerance matters (below). It is enough to say the geometry works and not
enough to put a figure on how well.

## From this project's own perception

The run above uses positions the dataset provides. The question that decides
whether any of this works on unannotated footage is what happens when the
positions come from here instead: RF-DETR tiled over the panorama, foot points
mapped to the pitch by a polynomial fitted against known positions
(`docs/DECISIONS.md`, D9).

On 118577's second half, mapping error against the annotated positions is
**1.74 m median, 2.71 m RMSE**.

| Corner radius | People in box | Candidates | Recall | Precision |
|---|---|---|---|---|
| 3 m (the setting used above) | 10 | 0 | 0.00 | — |
| 5 m | 10 | 6 | 0.60 | 0.50 |
| **6 m** | **12** | **7** | **1.00** | **0.71** |
| 8 m | 14 | 6 | 1.00 | 0.83 |

**The heuristic does not survive perception unchanged.** At the 3 m radius that
works perfectly on the provided positions, the pipeline built here finds
nothing at all: a 1.7 m median error, plus a detector that puts the corner
taker a metre or two off the flag, is enough to empty the test. Widening the
radius to 6 m recovers every corner at the cost of one extra candidate.

**These settings were chosen by looking at this half's score, so 1.00 and 0.71
are optimistic.** They were then run unchanged on a half they had never seen.

## The same settings on an unseen half: it does not transfer

128058's second half, seven corners, radius 6 m and twelve people in the box,
nothing adjusted:

| | 118577 (tuned on) | 128058 (unseen) |
|---|---|---|
| Recall | 1.00 | **0.43** (3 of 7) |
| Precision | 0.71 | **0.25** (9 spurious) |
| Candidates | 7 | 12 |

Sweeping the settings on 128058 does not rescue it either — the best recall any
combination reaches is 0.71, at a precision of 0.31. So the earlier 1.00 / 0.71
was five corners' worth of overfitting, and this is the number that counts.

### Why it fails, measured at the seven corner moments

For each labelled corner, the distance from the nearest tracked person to the
corner flag, and the number of people inside that penalty area:

| Corner | Own: nearest to flag | Own: in box | Annotated: nearest | Annotated: in box |
|---|---|---|---|---|
| 05:33 | 19.3 m | 10 | 4.3 m | 16 |
| 21:26 | 22.4 m | 15 | 4.3 m | 15 |
| 28:36 | 4.9 m | 10 | 5.4 m | 15 |
| 29:26 | 5.5 m | 15 | 4.3 m | 16 |
| 31:48 | 7.1 m | 10 | 2.2 m | 19 |
| 33:27 | 7.5 m | 12 | 2.2 m | 18 |
| 34:17 | 7.1 m | 12 | 3.1 m | 18 |

**The crowd survives perception and the taker does not.** People in the box come
out at 10 to 15 against the annotation's 15 to 19 — enough for any sensible
threshold. The corner taker is a different matter: twice they are not found at
all (19 m and 22 m to the nearest person, meaning the nearest person is someone
else entirely), and where they are found they land 5 to 7.5 m from the flag
against the annotation's 2 to 5.

That is the specific thing that breaks. A lone player at the edge of a stitched
panorama, at the extreme of the lens and with nothing beside them to help, is
the hardest detection on the pitch, and the heuristic leans its whole weight on
exactly that one person.

### What this says about the design

The next version should not depend on locating one player. The signals that did
survive are the ones about the whole configuration: almost everyone in one
penalty area, both teams present, play stopped. A corner detector built on the
crowd, using the corner region only as a weak prior rather than a requirement,
is the thing to try - and it should be tried on 128058 and checked on a third
half, not the other way round.

## Detection recall collapses where it matters

Measured on the five corner frames of 118577's second half, against the 22
people the annotation lists:

| Tiling | People found |
|---|---|
| 4 x 1 | 14, 14, 14, 14, 14 |
| 8 x 2 | 31, 30, 25, 23, 20 |
| 8 x 2, larger model | 37, 39, 30, 33, 28 |

With a 4 x 1 grid the corner taker was not among them in any of the five. A
corner is the most crowded moment in a match, players overlap, and the
detector fails hardest exactly where the tool is looking. Counts above 22 are
people off the pitch — substitutes, staff, another match in the background —
which the pitch-position filter removes.

The mapping error improved from 2.54 m to 1.74 m median on the finer grid,
without any change to the fitting code: more detections, better correspondences.

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

- **A corner detector that does not depend on one player being found.** The
  redesign the section above argues for has not been written, let alone
  measured.
- **Any match outside the two development halves.** The dataset's own test
  split (128057, 132831) has not been touched and should stay untouched until
  the settings stop moving.
- **Other set pieces.** Only corners are implemented.
- **Footage from a camera nobody annotated.** The mapping from pixels to metres
  is fitted against known positions, so every number here assumes the geometry
  is solved. On a phone on a tripod at a university match it would not be, and
  that is the gap between this measurement and a usable tool.
