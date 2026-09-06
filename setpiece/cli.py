"""Command line entry point: ``setpiece <command>`` or ``python -m setpiece``."""

import argparse
import sys

from . import __version__, corners, evaluate, labels, soccertrack, timecode, video


def _info(args):
    info = video.probe(args.video)
    estimated = " (estimated)" if info.frame_count_is_estimated else ""
    print(f"file:       {info.path}")
    print(f"resolution: {info.width}x{info.height}  ({info.megapixels:.1f} MP)")
    print(f"codec:      {info.codec}")
    print(f"frame rate: {info.fps:.3f} fps")
    print(f"duration:   {timecode.format(info.duration)}  ({info.duration:.1f}s)")
    print(f"frames:     {info.frame_count:,}{estimated}")
    print()
    for rate in args.sample_fps:
        count = len(video.sample_times(info, rate))
        share = count / info.frame_count if info.frame_count else 0
        print(f"coarse pass at {rate:g} fps: {count:,} frames ({share:.1%} of the file)")
    return 0


def _evaluate(args):
    truth = labels.load(args.labels, allow_confidence=False)
    found = labels.load(args.candidates)
    duration = 0.0
    if args.video:
        duration = video.probe(args.video).duration
    elif args.duration:
        duration = timecode.parse(args.duration)

    result = evaluate.score(
        truth,
        found,
        tolerance=args.tolerance,
        event=args.event,
        require_team=args.require_team,
        min_confidence=args.min_confidence,
        duration=duration,
        clip_seconds=args.clip_seconds,
    )
    print(evaluate.report(result))
    if args.fail_under is not None and result.recall < args.fail_under:
        print(f"\nrecall {result.recall:.2f} is below --fail-under {args.fail_under:.2f}",
              file=sys.stderr)
        return 1
    return 0


def _template(args):
    example = [
        labels.Event(time=timecode.parse("00:12:31"), event="corner", team="home",
                     note="replace these rows with real ones"),
        labels.Event(time=timecode.parse("00:24:42"), event="corner", team="away"),
    ]
    labels.dump(example, sys.stdout, confidence=False)
    print(f"\n# events: {', '.join(labels.EVENTS)}", file=sys.stderr)
    print(f"# teams:  {', '.join(labels.TEAMS)} (optional)", file=sys.stderr)
    return 0


def _import_gsr(args):
    rows = soccertrack.import_game_state(args.annotations, args.destination)
    print(f"{rows:,} player positions -> {args.destination}")
    return 0


def _corners(args):
    frames = soccertrack.load_positions(args.positions)
    settings = corners.Settings(
        corner_radius=args.corner_radius,
        min_in_box=args.min_in_box,
        scan_fps=args.scan_fps,
        merge_gap=args.merge_gap,
    )
    found = corners.candidates(frames, args.fps, settings)
    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as handle:
            labels.dump(found, handle)
        print(f"{len(found)} candidates -> {args.output}", file=sys.stderr)
    else:
        labels.dump(found, sys.stdout)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="setpiece",
        description="Spot set-piece candidates in fixed wide-angle football footage.",
    )
    parser.add_argument("--version", action="version", version=f"setpiece {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    info = commands.add_parser("info", help="report what a video file is, and what a coarse pass would cost")
    info.add_argument("video")
    info.add_argument("--sample-fps", type=float, nargs="+", default=[2.0, 4.0],
                      help="coarse frame rates to cost out (default: 2 4)")
    info.set_defaults(handler=_info)

    template = commands.add_parser("template", help="print an empty ground-truth label file")
    template.set_defaults(handler=_template)

    scoring = commands.add_parser("evaluate", help="score a candidate list against ground truth")
    scoring.add_argument("labels", help="hand-labelled ground truth CSV")
    scoring.add_argument("candidates", help="candidate CSV produced by the spotter")
    scoring.add_argument("--event", help="score only this event type")
    scoring.add_argument("--tolerance", type=float, default=15.0,
                         help="seconds a candidate may be away from the label (default: 15)")
    scoring.add_argument("--require-team", action="store_true",
                         help="a candidate must also name the right team to count")
    scoring.add_argument("--min-confidence", type=float, default=0.0)
    scoring.add_argument("--clip-seconds", type=float, default=30.0,
                         help="length of a review clip, for the review-time figure (default: 30)")
    scoring.add_argument("--video", help="read the match duration from this file")
    scoring.add_argument("--duration", help="match duration, if the video is not to hand")
    scoring.add_argument("--fail-under", type=float,
                         help="exit non-zero if recall falls below this")
    scoring.set_defaults(handler=_evaluate)

    importer = commands.add_parser(
        "import-gsr", help="turn a SoccerTrack v2 game-state file into a position cache")
    importer.add_argument("annotations", help="path to <match>_<half>.json")
    importer.add_argument("destination", help="path to write, ending .csv.gz")
    importer.set_defaults(handler=_import_gsr)

    spotter = commands.add_parser(
        "corners", help="find corner candidates in a position cache")
    spotter.add_argument("positions", help="cache written by import-gsr")
    spotter.add_argument("--fps", type=float, default=25.0,
                         help="frame rate of the annotated video (default: 25)")
    spotter.add_argument("--output", help="write candidates here instead of stdout")
    spotter.add_argument("--corner-radius", type=float, default=corners.Settings.corner_radius)
    spotter.add_argument("--min-in-box", type=int, default=corners.Settings.min_in_box)
    spotter.add_argument("--scan-fps", type=float, default=corners.Settings.scan_fps)
    spotter.add_argument("--merge-gap", type=float, default=corners.Settings.merge_gap)
    spotter.set_defaults(handler=_corners)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (video.VideoError, labels.LabelError, timecode.TimecodeError,
            soccertrack.AnnotationError, ValueError) as error:
        print(f"setpiece: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
