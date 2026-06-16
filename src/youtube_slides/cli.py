from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .images import CropRegion
from .pipeline import ExtractConfig, extract_slides, parse_timestamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slidewright",
        description="Extract distinct presentation slides from a YouTube URL or local video.",
    )
    parser.add_argument("source", help="YouTube URL or local video file")
    parser.add_argument("-o", "--output", default="slides", help="output directory")
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=2.0,
        help="seconds between sampled frames (default: 2.0)",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=int,
        default=20,
        help="perceptual hash distance for duplicate slides (default: 20)",
    )
    parser.add_argument(
        "--thumb-threshold",
        type=float,
        default=10.0,
        help="average thumbnail luma delta for duplicate slides (default: 10.0)",
    )
    parser.add_argument(
        "--min-slide-score",
        type=float,
        default=0.08,
        help="minimum slide-likeness score from 0 to 1 (default: 0.08)",
    )
    parser.add_argument(
        "--min-stable-samples",
        type=int,
        default=1,
        help="require a slide to appear in at least this many sampled frames (default: 1)",
    )
    parser.add_argument("--start", default="0", help="start time in seconds or HH:MM:SS")
    parser.add_argument("--end", default=None, help="end time in seconds or HH:MM:SS")
    parser.add_argument(
        "--crop",
        default=None,
        help="crop region x,y,w,h applied before hashing and export",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=1280,
        help="scale sampled frames down to this width, preserving aspect (default: 1280)",
    )
    parser.add_argument(
        "--allow-repeats",
        action="store_true",
        help="keep repeated slides if they reappear later",
    )
    parser.add_argument(
        "--no-contact-sheet",
        action="store_true",
        help="do not write index.html",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="keep intermediate PPM frames in output/work",
    )
    parser.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg executable")
    parser.add_argument("--ytdlp", default="yt-dlp", help="yt-dlp executable")
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        metavar="BROWSER",
        help="load YouTube cookies from a browser such as chrome, edge, firefox, safari, or brave",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        crop = CropRegion.parse(args.crop) if args.crop else None
        config = ExtractConfig(
            sample_interval=args.sample_interval,
            similarity_threshold=args.similarity_threshold,
            thumb_threshold=args.thumb_threshold,
            min_slide_score=args.min_slide_score,
            min_stable_samples=args.min_stable_samples,
            start=parse_timestamp(args.start),
            end=parse_timestamp(args.end) if args.end else None,
            max_width=args.max_width,
            crop=crop,
            allow_repeats=args.allow_repeats,
            write_contact_sheet=not args.no_contact_sheet,
            keep_work_dir=args.keep_work_dir,
            ffmpeg=args.ffmpeg,
            ytdlp=args.ytdlp,
            cookie_browser=args.cookies_from_browser,
        )
        result = extract_slides(args.source, Path(args.output), config)
    except Exception as exc:
        print(f"slidewright: {exc}", file=sys.stderr)
        return 1

    print(f"sampled {result.sampled_frames} frames")
    print(f"extracted {len(result.slides)} slides")
    print(f"wrote {result.manifest_path}")
    if result.work_dir is not None:
        print(f"kept work directory {result.work_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
