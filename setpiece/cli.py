"""Command line entry point: ``setpiece <command>`` or ``python -m setpiece``."""

import argparse
import sys

from . import (__version__, corners, detect, evaluate, labels, soccertrack,
               timecode, video)


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


def _detect(args):
    """Run the detector over a video and cache what it found."""
    def progress(frame, seconds, written):
        print(f"{timecode.format(seconds)}  {written:,} detections",
              file=sys.stderr)

    written = detect.detect_video(
        args.video,
        args.destination,
        sample_fps=args.sample_fps,
        columns=args.columns,
        rows=args.rows,
        overlap=args.overlap,
        threshold=args.threshold,
        limit=args.limit,
        progress=progress if args.progress else None,
    )
    print(f"{written:,} detections -> {args.destination}")
    return 0


def _map_detections(args):
    """Turn a detection cache into the position cache the spotter reads."""
    import csv
    import gzip

    from . import pitchmap

    detections = detect.load_detections(args.detections)
    reference = soccertrack.load_positions(args.reference)

    # Frames used for the fit are spread across the half rather than taken from
    # its start: a camera does not move, but the light and the crowding do.
    shared = sorted(set(detections) & set(reference))
    if not shared:
        raise ValueError("no frame appears in both the detections and the reference")
    chosen = shared[:: max(1, len(shared) // args.fit_frames)]
    pairs = [([detect.foot_point(box) for box in detections[frame]],
              [(row[3], row[4]) for row in reference[frame]])
             for frame in chosen]
    model, history = pitchmap.fit_by_alignment(pairs, degree=args.degree)
    last = history[-1]
    print(f"fitted on {len(chosen)} frames, {last['pairs']} pairs: "
          f"RMSE {last['rmse']:.2f} m, median {last['median']:.2f} m", file=sys.stderr)

    written = 0
    with gzip.open(args.destination, "wt", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(soccertrack.COLUMNS)
        dropped = 0
        for frame in sorted(detections):
            boxes = detections[frame]
            if not boxes:
                continue
            placed = model([detect.foot_point(box) for box in boxes])
            keep = pitchmap.on_pitch(placed, args.margin)
            dropped += int((~keep).sum())
            for (x, y) in placed[keep]:
                writer.writerow([frame, -1, "", "", round(float(x), 3), round(float(y), 3)])
                written += 1
        if dropped:
            print(f"dropped {dropped:,} detections that mapped off the pitch",
                  file=sys.stderr)
    print(f"{written:,} positions -> {args.destination}")
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

    finder = commands.add_parser(
        "detect", help="find people in a video and cache the boxes")
    finder.add_argument("video", help="path to the panorama")
    finder.add_argument("destination", help="detection cache to write, ending .csv")
    finder.add_argument("--sample-fps", type=float, default=4.0,
                        help="frames per second to run on (default: 4)")
    finder.add_argument("--columns", type=int, default=8,
                        help="tile columns (default: 8; see docs/RESULTS.md)")
    finder.add_argument("--rows", type=int, default=2, help="tile rows (default: 2)")
    finder.add_argument("--overlap", type=float, default=0.08,
                        help="how far tiles overlap, as a fraction (default: 0.08)")
    finder.add_argument("--threshold", type=float, default=0.4,
                        help="minimum detection score (default: 0.4)")
    finder.add_argument("--limit", type=int, help="stop after this many frames")
    finder.add_argument("--progress", action="store_true",
                        help="report progress while running")
    finder.set_defaults(handler=_detect)

    mapper = commands.add_parser(
        "map-detections",
        help="place detections on the pitch, fitting the mapping against known positions")
    mapper.add_argument("detections", help="cache written by the detector")
    mapper.add_argument("reference", help="position cache from import-gsr, used to fit")
    mapper.add_argument("destination", help="position cache to write, ending .csv.gz")
    mapper.add_argument("--degree", type=int, default=3)
    mapper.add_argument("--fit-frames", type=int, default=60,
                        help="how many frames to fit on (default: 60)")
    mapper.add_argument("--margin", type=float, default=12.0,
                        help="metres outside the pitch a detection may still land")
    mapper.set_defaults(handler=_map_detections)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (video.VideoError, labels.LabelError, timecode.TimecodeError,
            soccertrack.AnnotationError, detect.DetectorError, ValueError) as error:
        print(f"setpiece: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
