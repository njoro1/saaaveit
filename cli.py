#!/usr/bin/env python3
"""Command-line front end for the Saaaveit.

Uses the same engine as the GUI (``src.media_source``) so a CLI download and a
GUI download are byte-for-byte the same operation.

Examples::

    python cli.py --list-formats URL
    python cli.py URL --codec vp9 --resolution 1080 --subs ja
    python cli.py URL --subs-only --subs ja -o C:\\Downloads
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import media_source  # noqa: E402
from src.store import DEFAULT_FILENAME_TEMPLATE  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="saaaveit",
        description="Inspect and download a video and one subtitle track.",
    )
    parser.add_argument("url", help="Video URL (watch, short, embed).")
    parser.add_argument("-o", "--out-dir", default=os.getcwd(), help="Where to save files.")
    parser.add_argument(
        "--filename-template",
        default=DEFAULT_FILENAME_TEMPLATE,
        help="yt-dlp output template (default: %(default)s).",
    )
    parser.add_argument("--list-formats", action="store_true", help="Print available formats and exit.")
    parser.add_argument("--codec", default="best", choices=["best", "av1", "vp9", "h264"])
    parser.add_argument("--resolution", default="best", help='"best" or a height such as 1080.')
    parser.add_argument("--subs", default="", help="Subtitle language code to download, e.g. ja.")
    parser.add_argument(
        "--subs-kind",
        default="",
        choices=["", "manual", "auto"],
        help="Restrict the subtitle track to manual or auto-generated.",
    )
    parser.add_argument("--subs-only", action="store_true", help="Download only the subtitle track.")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON.")
    return parser


def _print_formats(info: dict) -> None:
    print(f"{info.get('title') or '(untitled)'}  [{info.get('video_id')}]")
    language = info.get("language") or "unknown"
    print(f"Original language: {language}")
    print("")
    print(f"{'CODEC':10} {'RES':8} {'SIZE':10} STREAM")
    for cid in info.get("codecs") or []:
        for height, option in sorted((info.get("matrix") or {}).get(cid, {}).items(), reverse=True):
            size = option.get("filesize") or 0
            size_text = f"{size / 1048576:.1f}MB" if size else "—"
            print(f"{cid:10} {int(height):<8} {size_text:10} {option.get('format_selector', '')}")
    print("")
    tracks = info.get("subtitle_tracks") or []
    if not tracks:
        print("Subtitle tracks: none")
        return
    print("Subtitle tracks:")
    default = info.get("default_subtitle_track") or ""
    for track in tracks:
        marker = "*" if track.get("code") == default else " "
        print(f" {marker} {track.get('code'):10} {track.get('kind'):7} {track.get('name')}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        info = media_source.inspect_video(args.url)
    except Exception as exc:  # noqa: BLE001 - reported to the caller
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.list_formats:
        _print_formats(info)
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    template = os.path.join(args.out_dir, args.filename_template)
    result: dict = {"video": "", "subtitle": ""}

    if not args.subs_only:
        option = media_source.resolve_video_option(info, args.codec, args.resolution)
        if not option:
            reason = media_source.describe_unavailable(info, args.codec, args.resolution)
            print(f"error: {reason}", file=sys.stderr)
            return 2
        try:
            result["video"] = media_source.download_video(
                args.url,
                option["format_selector"],
                template + ".%(ext)s",
                progress_cb=lambda line: print(line, flush=True),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"error: video download failed: {exc}", file=sys.stderr)
            if not args.subs:
                return 1

    if args.subs:
        try:
            result["subtitle"] = media_source.download_subtitle(
                args.url,
                args.subs,
                template,
                progress_cb=lambda line: print(line, flush=True),
                kind=args.subs_kind,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"error: subtitle download failed: {exc}", file=sys.stderr)
            if not result["video"]:
                return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for kind, path in result.items():
            if path:
                print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
