# SoccerTrack v2, as actually encountered

Everything here was measured against the released files, not read off the
dataset card. Where the two disagree the card is quoted, so the difference is
visible rather than silently corrected.

Checked 2026-09-06 against match 118577, second half.

## Downloading

**`hf download` can finish successfully and leave a zero-byte file.** It
happened on 15 of the 20 game-state files and on the first attempt at a video.
The command exits 0 and prints the destination path; only the file size shows
that nothing arrived. Disabling the Xet transport fixes it:

```bash
HF_HUB_DISABLE_XET=1 hf download atomscott/soccertrack-v2 --repo-type dataset \
  --include "videos/118577/118577_panorama_2nd_half.mp4" --local-dir data/soccertrack-v2
```

Check sizes after every download, and delete the empty files before retrying —
a zero-byte file already in place is treated as present and skipped.

## What the files contain

| | |
|---|---|
| Video | 4096 x 1080, H.264, 25 fps, 48:19, 72,475 frames, 3.3 GB for one half |
| Game state | one JSON per half, 2.5-2.7 GB, pretty-printed |
| Player positions inside it | 1,599,683 rows for one half — about 1% of the bytes |

The game-state file is mostly pitch-line annotations repeated for every frame.
`setpiece import-gsr` streams it and writes the player positions as a 4.4 MB
gzipped CSV in under two minutes.

**The annotation and the video have different frame sizes.** Annotated images
are 3840 x 1504; the distributed video is 4096 x 1080. Pixel coordinates
(`bbox_image`) therefore cannot be drawn on the video without a transform.
Pitch coordinates (`bbox_pitch`, metres) are unaffected, and are what this
project uses.

The `info` block is boilerplate — `game_id` "7", `id` "1", `game_time_start`
"1 - 00:00" and `clip_stop` 30000 are identical in every file, including the
second halves. Only `seq_length` is real.

## Timing

The annotation runs 72,751 frames and the video 72,475 — a difference of 276
frames, about 11 seconds. Checked at 454 s by cutting the frame and looking at
it: the annotation has 16 people in the left penalty area and one player on the
corner flag, and the video shows the same crowd around the same goal with the
far end empty. The two are aligned to within a few seconds, which is inside the
tolerance the evaluator uses.

Event timestamps in `bas/` are **cumulative from the start of the match**, not
from the start of the half: the second half of 118577 begins at
`position` 2,699,520 ms. Subtract the first second-half position before
comparing with a video time.

## The ball track cannot be used to find restarts

`ball/` gives a per-frame position, but on 117092:

- `status == 1` (tracked) covers 21,444 of 67,374 frames — **32%**.
- Of 123 `OUT` events, **110 have no tracked ball position in the preceding
  four seconds**, so where the ball left play is unknown for most stoppages.
- Untracked frames are **clamped to the pitch rectangle**, which puts the ball
  at exactly (52.5, -34.0) — the corner flag. Searching for "a ball near a
  corner" returns those clamped frames, five of them in this match, every one a
  false positive that looks like a clean detection.

The card notes clamping for matches 132831 and 132877. It happens in 117092 as
well.

This is why `setpiece corners` uses player positions only.

## `raw/` contains a full commercial event feed

`<match>_player_nodes.csv` is not a list of nodes. It is a match event feed with
a 401-token vocabulary, one row per event, carrying `event_time`,
`event_period`, team, normalised position, and the players involved.

It includes the set-piece labels the ball-action annotation does not:

| Token | Count in 118577 |
|---|---|
| `throwIn` | 44 |
| `freeKick` | 16 |
| `goalKickFailed` / `goalKickSucceeded` | 14 / 7 |
| **`cornerKick`** | **11** (6 in the first half, 5 in the second) |

This is the ground truth for corners, and it is independent of the player
tracking, so a detector built on player geometry can be scored against it
honestly. `setpiece`'s `corner_labels()` reads it.

`event_time` is cumulative from the start of the match, like `bas/`. The feed
reports `SECOND_HALF` starting at 2,700,000 ms while `bas/` starts it at
2,699,520 ms; the 480 ms difference is well inside the tolerance used for
scoring, but it is a real disagreement between two files in the same release.

**This file also contains the players' real names.** See
[DATA_POLICY.md](DATA_POLICY.md).

## The bundled calibration does not project as expected

`raw/` ships `homography.npy` (3x3), `mapx.npy` (1080, 4096, 2) int16 and
`mapy.npy` (1080, 4096) uint16 — the map shapes match the distributed video
exactly. The homography, however, does not take pitch metres to video pixels in
either the centre-origin or the corner-origin convention: all 22 players of a
frame project into a band about 150 px wide, and running `cv2.remap` with the
supplied maps produces a squashed image rather than an undistorted one.

Some further step is implied that the release does not document. Until it is
worked out, this project uses pitch coordinates directly and does not draw on
the video. Overlaying ground truth on frames needs this resolved.
