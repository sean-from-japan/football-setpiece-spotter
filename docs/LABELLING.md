[日本語](LABELLING.ja.md) | English

# Labelling a match

The ground truth is written before the detector, because a detector built first
gets scored against labels that were quietly shaped to flatter it.

## Format

One CSV per match, kept beside the footage under `data/`, never committed:

```csv
time,event,team,note
00:12:31,corner,home,short corner
00:24:42,corner,away,
00:38:51,corner,home,cleared straight out
```

`setpiece template` prints an empty one with the accepted vocabulary.

- **time** — when the restart is *taken*, not when the ball went out and not
  when the referee blew. `12:31`, `00:12:31` and `751` all mean the same
  instant.
- **event** — one of `corner`, `throw_in`, `free_kick`, `goal_kick`,
  `kick_off`, `penalty`, `goal`.
- **team** — optional. Fill it only if you are labelling a match where you can
  tell the sides apart at wide-angle scale in every part of the pitch.
- **note** — free text, for anything that will matter when a candidate near
  this timestamp is argued about.

## Protocol

1. Label at 1x with a stopwatch overlay, not by scrubbing. Scrubbing finds the
   corners you remember.
2. Label the whole match, including the half you expect to be quiet. Recall is
   only meaningful over a complete match.
3. Record the timestamp of kick-off in each half. Side changes at half time are
   what make an attacking-direction estimate falsifiable.
4. Label one match **twice**, on different days, and score the second pass
   against the first with `setpiece evaluate`. That number is the ceiling — a
   detector cannot be shown to be better than the labelling is consistent, and
   the disagreement between two human passes is what sets the tolerance used
   everywhere else.

## Why the tolerance is generous

The output of this tool is a clip a human opens, currently 30 seconds long. A
candidate ten seconds early still shows the reviewer the right restart, so
scoring it as a miss would measure something the reviewer never experiences.
The default is ±15 s, and it should be reported next to every number, because
recall at ±15 s and recall at ±2 s are different claims.
