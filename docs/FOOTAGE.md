[日本語](FOOTAGE.ja.md) | English

# Where the footage comes from

The project needs whole matches from a **fixed wide camera**, because the claim
being tested is about that camera. Broadcast footage cuts, zooms and replays,
and a corner in a broadcast is announced by the director's camera change — a
signal that does not exist on a touchline camera and would flatter any detector
evaluated on it.

Checked 2026-09-05.

## First choice — SoccerTrack v2

| | |
|---|---|
| What | 10 university-level matches, 934 minutes, 4K panorama, 145 GB in total |
| Camera | BePro fixed multi-camera panoramic stitching (8 matches) and BePro Cerberus (2) |
| Licence | CC BY 4.0, pseudonymised — names replaced by jersey numbers |
| Access | Hugging Face `atomscott/soccertrack-v2`, gated: an account and an accepted agreement are required |
| Paper | [arXiv:2508.01802](https://arxiv.org/abs/2508.01802) |
| Also ships | Game-state annotations, ball-action events, per-frame ball tracks, and per-match pitch calibration |

Contents, from the dataset card:

| Folder | What is in it |
|---|---|
| `videos/` | 20 panoramic half-match videos, two 45-minute periods per match |
| `gsr/` | Frame-level game state per half: pitch coordinates, jersey-derived identities, roles, team sides |
| `bas/` | Ball action events, 12 classes, with acting team and actor |
| `ball/` | Per-frame ball track per half |
| `mot/` | The MMSports 2025 challenge subset: 4-minute clips with boxes |
| `raw/` | Per-match pitch keypoints, distortion maps and camera intrinsics |

Splits are fixed: test 128057 and 132831, validation 117093 and 132877, the
remaining six for training. Pitch coordinates are metric on 105 x 68 m with the
origin at the centre circle.

This is the closest public match to the target domain there is: university
football, a fixed panoramic camera, whole halves rather than clips, and a
licence that permits use with attribution. It comes from the same population as
this author's `togakuren-analytics`, which analyses Japanese university league
records.

**Corner is not one of the 12 annotated action classes.** The list is Pass,
Drive, Header, High Pass, Out, Cross, Throw In, Shot, Ball Player Block, Player
Successful Tackle, Free Kick, Goal. So the corner ground truth still has to be
labelled by hand — which is the work this project was going to do anyway — and
the existing labels become an independent cross-check: an `Out` followed by a
`Cross` from a corner region is a corner, and disagreement between that
reconstruction and the hand labels is a measurement of the labelling itself.

## Downloading it

145 GB is not downloaded in one go and does not need to be. The order is:

1. **Annotations only** — `gsr/`, `bas/`, `ball/`, `raw/`. Small, and enough to
   build and measure the corner spotter against provided tracks (see D8).
2. **One half at a time** — 3.3 GB for the half measured so far. Sample it,
   cache the detections, then delete the video. The cache is what later work
   reads; the file itself is needed once. Pass `HF_HUB_DISABLE_XET=1` and check
   the file size afterwards: see [DATASET_NOTES.md](DATASET_NOTES.md).
3. **More halves only when the measurement needs them** — the two test matches
   stay untouched until the detector stops changing.

## Backup — Alfheim (Simula)

3 whole Tromsø IL matches (2013), stitched panorama from fixed camera arrays at
the halfway line, plus 20 Hz player positions from a body-sensor system. Free
for research with citation, no gate: <https://datasets.simula.no/alfheim/>.

Professional rather than amateur, and eleven years older, so it is the fallback
if SoccerTrack v2 access does not come through — and a useful contrast if it
does, because the same detector on professional and university footage is a
comparison nobody has published.

## Not suitable

- **SoccerNet / SN-spotting / FOOTPASS** — broadcast footage from European
  leagues. Excellent for comparison to published action-spotting numbers, wrong
  for the question this project asks.
- **The 62-second Creative Commons clip** named in the original brief — enough
  to prove the pipeline runs, not enough to produce a recall figure. One clip
  has no corners to miss.

## Own footage

Still worth having eventually. A camera on a tripod at a Japanese university
match is the exact deployment being argued for, and one such match would show
whether a result obtained on BePro panoramas survives a phone on a tripod.
Recording other people requires their agreement in advance; see
[DATA_POLICY.md](DATA_POLICY.md).
