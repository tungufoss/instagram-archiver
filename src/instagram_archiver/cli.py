"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .archive import Summary, archive_post, archive_profile
from .indexing import load_known_hashes, write_index
from .paths import default_browser_profile_dir, default_output_dir
from .scraper import PrivateProfile, VideoSniffer
from .session import NotLoggedIn, browser_session, ensure_login
from .urls import normalise_post_url

EPILOG = """\
examples:
  instagram-archiver login
  instagram-archiver profile https://www.instagram.com/someaccount/
  instagram-archiver profile https://www.instagram.com/someaccount/ --max-posts 3
  instagram-archiver post https://www.instagram.com/p/ABC123/

This tool only saves what your own logged-in account can already see. It does
not bypass private-account restrictions, and it never reads your password.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instagram-archiver",
        description="Archive Instagram photos and videos your account can already see.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="where to save media (default: ./ig_archiver in the current "
             "directory). Each account gets its own subfolder there.",
    )
    parser.add_argument(
        "--browser-profile", type=Path, default=None,
        help="persistent browser profile directory "
             "(default: a per-user application data directory)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="run without a window (only after `login` has succeeded once)",
    )
    parser.add_argument(
        "--skip-videos", action="store_true", help="save photographs only",
    )
    parser.add_argument(
        "--include-reels", action="store_true",
        help="also archive reels listed on a profile. Off by default: a reel is "
             "usually the same video already attached to a post",
    )
    parser.add_argument(
        "--flatten", action="store_true",
        help="put an account's files straight in its folder, without a folder "
             "per post; filenames are prefixed with date and post ID",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="open a window and wait for manual login")
    login.set_defaults(url=None, max_posts=None)

    profile = sub.add_parser("profile", help="archive every visible post on a profile")
    profile.add_argument("url", help="profile URL")
    profile.add_argument(
        "--max-posts", type=int, default=None,
        help="stop after N posts (useful for a first test run)",
    )

    post = sub.add_parser("post", help="archive one specific post URL")
    post.add_argument("url", help="post or reel URL")
    post.set_defaults(max_posts=None)

    return parser


def print_summary(summary: Summary, out_dir: Path) -> None:
    print()
    print("=" * 50)
    print(f"Posts visited        : {summary.posts_visited}")
    print(f"Posts yielding media : {summary.posts_with_media}")
    print(f"Images downloaded    : {summary.images}")
    print(f"Videos downloaded    : {summary.videos}")
    print(f"Saved under          : {out_dir}")
    if summary.records:
        print("Index files          : index.csv, index.json")
    print("=" * 50)


def _prepare_output() -> None:
    """Make output safe and live.

    Windows consoles default to cp1252, which crashes on emoji in captions.
    Line buffering matters when output is piped to a log file: without it
    Python block-buffers and a long run appears to produce nothing for
    minutes at a time.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace",
                               line_buffering=True)
        except (AttributeError, OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _prepare_output()
    args = build_parser().parse_args(argv)

    out_dir = (args.out or default_output_dir()).resolve()
    profile_dir = (args.browser_profile or default_browser_profile_dir()).resolve()
    headless = args.headless and args.command != "login"
    want_videos = not args.skip_videos

    if want_videos and args.command != "login":
        print("=" * 70)
        print(" WARNING: video downloading is unreliable and can save the WRONG")
        print(" video. Instagram prefetches unrelated videos on every page, and")
        print(" this tool cannot always tell which file belongs to which slide.")
        print(" Photographs are not affected.")
        print("")
        print(" Use --skip-videos for an archive you can trust.")
        print(" See https://github.com/tungufoss/instagram-archiver/issues/8")
        print("=" * 70)
        print("")

    hashes = load_known_hashes(out_dir)
    summary = Summary()

    try:
        with browser_session(profile_dir, headless=headless) as (context, page):
            sniffer = VideoSniffer(page)
            ensure_login(context, page)

            if args.command == "login":
                print("Login step complete - nothing downloaded.")
                return 0

            try:
                if args.command == "post":
                    post_url = normalise_post_url(args.url)
                    if not post_url:
                        print(f"Not an Instagram post/reel URL: {args.url}", file=sys.stderr)
                        return 2
                    summary = archive_post(
                        context, page, sniffer, post_url, out_dir, hashes,
                        want_videos, args.flatten,
                    )
                else:
                    summary = archive_profile(
                        context, page, sniffer, args.url, out_dir, hashes,
                        want_videos, args.max_posts, args.flatten,
                        args.include_reels,
                    )
            finally:
                # archive_* writes after each post; this catches anything that
                # was collected before an error interrupted the loop.
                write_index(out_dir, summary.records)

    except PrivateProfile as exc:
        print(exc, file=sys.stderr)
        return 1
    except NotLoggedIn as exc:
        print(exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130

    print_summary(summary, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
