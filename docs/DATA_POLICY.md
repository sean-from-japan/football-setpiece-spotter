[日本語](DATA_POLICY.ja.md) | English

# Data policy

The repository contains code. It contains no match footage, no extracted
frames, no label files and no model weights, and CI fails if any of those are
committed.

The people in this footage are amateur student players. A club or a federation
choosing to record a match is not consent for a third party to redistribute
video of the individuals in it, and video is a far more identifying record than
the appearance data this author has already published policy for in
[togakuren-analytics](https://github.com/sean-from-japan/togakuren-analytics).

Consequences for anyone running this:

- Footage stays under `data/`, which is git-ignored. Keep it where the team that
  recorded it agreed it would be kept.
- Label files name events, not people. There is no player-identity column, and
  jersey-number recognition is explicitly out of scope.
- Anything published from a run — a figure, a results table, a README number —
  is aggregate: counts, recall, review time. Not clips, not stills, not tracks
  of a named individual.
- Before using footage recorded by someone else, get their agreement in writing
  for the specific use, including whether any frame may appear in a public
  report.

## The dataset is not as pseudonymised as its card says

SoccerTrack v2's card states: the release is pseudonymised, personal names
replaced by jersey numbers. That holds for `gsr/`, `bas/` and `mot/`.

It does not hold for `raw/`. Each `<match>_player_nodes.csv` carries the
**players' real given and family names**, their shirt numbers and their club
name, alongside a per-event feed. Match 118577's file has 2,384 such rows.

Consequences for this repository, in addition to everything above:

- `raw/` is data, and data is not committed. Nothing changes there.
- Code that reads `raw/` reads **only** the fields it needs. `corner_labels()`
  takes the timestamp, the period and the team id, and no name ever enters the
  program.
- Nothing derived from `raw/` is published with a name in it, including in
  examples, figures and commit messages.
- The maintainers should be told; a card that promises pseudonymisation and a
  file that carries names is a problem for the students in it, not only for the
  people using the data.
