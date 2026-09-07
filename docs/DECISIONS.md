# Decisions

Every entry records a choice that a reader would otherwise have to guess at, the
evidence behind it, and what would make it wrong.

## D1. The pipeline is not the deliverable; the measurement is

Detection → tracking → team clustering → homography → possession is a solved,
widely copied recipe. `roboflow/sports` ships it as a library, and a search of
public repositories returns a long tail of near-identical rebuilds of it
(YOLOv5/v8/v9 + ByteTrack + a bird's-eye view). Rebuilding that produces nothing
a reader cannot already download.

What is not in those repositories is an answer to the question an amateur team's
analyst actually has:

> Given 90 minutes of fixed wide-angle footage, how many minutes must a human
> still watch to find every corner, and how many corners does the tool miss?

So the pipeline here exists only to feed a **measured** set-piece spotter, and
the headline numbers of this project are recall, the number of candidate clips,
and the review time they imply — not a demo video with boxes drawn on it.

Consequence: ground truth is labelled **before** the detector is written
(`docs/LABELLING.md`), and a detector change that is not accompanied by a
`setpiece evaluate` run does not ship.

## D2. RF-DETR before Ultralytics YOLO

The project brief named Ultralytics YOLO as the first detector. Ultralytics is
licensed **AGPL-3.0**, which is a strong copyleft: a public repository that
imports it is expected to carry AGPL terms outward, which conflicts with the MIT
licence used across the rest of this author's public work, and would follow any
later non-open use of this code.

RF-DETR (Roboflow) is **Apache-2.0**, code and weights, with no copyleft
obligation.

Decision: the detector is loaded behind an interface (`setpiece/detect.py`)
whose default backend is RF-DETR. An Ultralytics backend may be added as an
opt-in extra, kept out of the default dependency set, so that installing this
project does not pull an AGPL dependency in.

Wrong if: RF-DETR's football-domain accuracy on wide amateur footage proves
materially worse than a YOLO checkpoint fine-tuned on football. That is a
measurement, and it belongs in `docs/RESULTS.md`, not in an assumption.

## D3. Everything except model inference is standard library

`ffprobe`/`ffmpeg` are already required for reading and cutting video, so the
video layer, the cache, the label format and the evaluator need no third-party
package and no compiled wheel. Tests therefore run on any Python 3.9+ with no
network, no GPU and no model download, which is what keeps CI honest on three
operating systems.

Only `setpiece/detect.py` and the tracking layer require torch, and it is
imported inside the function that runs the model rather than at the top of
the module. `setpiece/pitchmap.py` is the one other exception: fitting the
mapping needs numpy and scipy, which ship with the same `detect` extra.

## D4. Coarse-to-fine, not full-frame-rate inference

A 90-minute 30 fps match is 162,000 frames. Sampling at 4 fps is 21,600. Set
pieces are seconds-long events preceded by a stoppage, so the coarse pass loses
nothing that matters; only the neighbourhood of a candidate is re-read densely.
This is a stated constraint of the target machine (Apple Silicon, MPS, no CUDA),
not a preference.

## D5. No footage in this repository, ever

The subjects are amateur student players. The federation publishing a fixture
list is not consent for a third party to redistribute video of them. The
repository holds code; `data/` is ignored and CI fails if video, frames or
labels are committed. This mirrors the data policy of the author's
`togakuren-analytics`, where the same reasoning was worked out in detail.

## D6. Public panorama footage, not only footage of one's own

The brief assumed footage would come from a camera the author controls, and none
was to hand. It turns out the domain has a public dataset that fits it exactly:
**SoccerTrack v2** — 10 university matches, ~900 minutes, fixed BePro panoramic
4K, CC BY 4.0. Whole halves, not clips, so recall over a complete match is
measurable, and the population is the same one `togakuren-analytics` already
covers.

Decision: develop and measure against SoccerTrack v2 first, treat Alfheim as the
professional-football contrast, and treat footage recorded by the author as the
deployment test rather than as the prerequisite. See
[FOOTAGE.md](FOOTAGE.md).

## D7. Tiling is a requirement, not an optimisation (measured 2026-09-05)

Measured on the target machine — Apple M5, 24 GB, `rfdetr` 1.10.0, torch 2.14,
five runs after a warm-up, RF-DETR Nano (30.5 M parameters):

| Input | Seconds per frame |
|---|---|
| 1080p whole frame | 0.029 |
| 4K whole frame | 0.035 |
| 4K as 3x2 tiles of 1280x1080 | 0.187 |

Two things follow.

**A 4K frame costs almost the same as a 1080p one, because the model resizes
its input to 384x384 either way.** On a stitched panorama of a full pitch, that
leaves a player a few pixels tall and the ball smaller than one pixel. Whole-frame
inference on panoramic footage is therefore not a cheap first version to be
improved later — it cannot see the objects at all. The pipeline tiles from the
start, and the tile grid is a configuration value that gets measured, not
guessed.

**The budget is the tiled figure.** A coarse pass at 4 fps over a 45-minute half
is 10,800 frames, so roughly 34 minutes per half and about an hour per match at
3x2 tiles — acceptable for an overnight or background run on a laptop, which is
what the project claims to be.

Also measured: `RFDETRNano(device="mps")` still reports its parameters on `cpu`,
so the MPS path in the brief is not doing anything yet. It does not matter at
these numbers, and chasing it before there is a working detector would be
optimising a pipeline that does not exist.

## D8. Build the corner spotter on the provided tracks first

SoccerTrack v2 ships frame-level game state — every player in pitch coordinates
with a team side and a role, a per-frame ball track, and hand-annotated pitch
calibration for each match. That is the output of the entire detection →
tracking → team → homography chain, given as ground truth on the same footage
this project is evaluated on.

So the corner heuristic is written against those tracks **before** any detector
exists. Two consequences, both of which make the project stronger rather than
shorter:

1. The interesting question gets answered first. If corners cannot be spotted
   from *perfect* tracking, they certainly cannot be spotted from ours, and that
   is a result worth publishing after a week rather than after a month.
2. It separates two errors that are otherwise measured as one. Running the same
   heuristic on ground-truth tracks and then on our own gives the loss
   attributable to perception, as a number, instead of an excuse.

The pitch calibration in `raw/` also removes the homography milestone from the
critical path: for this dataset it is provided, and estimating it is only needed
for footage from a camera nobody calibrated — which is the deployment case, not
the measurement case.

## D9. The pitch mapping is fitted, and its cost is stated

The release's own homography does not take pitch metres to the pixels of the
distributed video in any convention that works, and a single homography would
be wrong regardless: the panorama is stitched from several cameras, so no one
projective transform describes it. `setpiece.pitchmap` fits a low-order
polynomial instead, from the annotated player positions, alternating between
pairing points and refitting because which detection is which player is not
known.

Measured on 118577's second half: **1.74 m median, 2.71 m RMSE** against the
annotated positions.

This is a deliberate loan from the ground truth, and it is what makes the
perception number meaningful: it isolates detection and tracking with the
geometry held correct. It also means no number in `docs/RESULTS.md` transfers
to a camera nobody has annotated. Calibrating an unknown camera is a separate
problem and is not solved here.

## Open

- **Access.** SoccerTrack v2 is gated on Hugging Face (automatic approval, but
  an account and an accepted licence are required), and the panorama halves are
  large. Nothing is downloaded until that is settled and the disk cost is known.
- **The corner labels do not exist anywhere.** Corner is not among the 12
  annotated action classes, so the ground truth is still hand-written work, one
  match at a time, following [LABELLING.md](LABELLING.md).
