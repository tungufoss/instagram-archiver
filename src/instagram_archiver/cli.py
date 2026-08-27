"""Command line interface."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__, logfile, relayout
from .archive import (
    Summary,
    archive_post,
    archive_profile,
    prune_empty_dirs,
    save_post,
)
from .config import POST_PAUSE
from .indexing import (
    load_archived_files,
    load_known_hashes,
    posts_missing_videos,
    write_index,
)
from .paths import default_browser_profile_dir, default_output_dir
from .progress import line as progress_line
from .scraper import PrivateProfile, nap
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


def _common_options(parser: argparse.ArgumentParser, default=None) -> None:
    """Options accepted both before and after the subcommand.

    argparse normally requires top-level flags to precede the subcommand, so
    `... profile URL --skip-videos` fails with an unhelpful usage error. These
    are registered in both places instead, because being picky about flag
    order is a trap, not a feature.

    The subcommand copies must use `default=SUPPRESS`: a subparser parses into
    a fresh namespace and then copies every attribute onto the parent one, so
    an ordinary default there would silently overwrite a value the user gave
    *before* the subcommand. SUPPRESS leaves the attribute unset instead, and
    nothing gets clobbered.
    """
    parser.add_argument(
        "--out", type=Path, default=default,
        help="where to save media (default: ./ig_archiver in the current "
             "directory). Each account gets its own subfolder there.",
    )
    parser.add_argument(
        "--browser-profile", type=Path, default=default,
        help="persistent browser profile directory "
             "(default: a per-user application data directory)",
    )
    parser.add_argument(
        "--headless", action="store_true", default=default,
        help="run without a window (only after `login` has succeeded once)",
    )
    parser.add_argument(
        "--videos", action="store_true", default=default,
        help="also download videos. Off by default so a photo archive stays "
             "a photo archive; a skipped video leaves a placeholder",
    )
    # Photographs-only is the default now, so this is a no-op. Kept because it
    # is what the flag used to be called and typing it should not be an error.
    parser.add_argument(
        "--skip-videos", action="store_true", default=default,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--include-reels", action="store_true", default=default,
        help="also archive reels listed on a profile. Off by default: they "
             "carry no photographs",
    )
    parser.add_argument(
        "--log", type=Path, default=default,
        help="where to write the run log (default: archive.log beside the "
             "media). Pass '-' to write no log",
    )
    parser.add_argument(
        "--resume", action="store_true", default=default,
        help="skip posts the index shows are already complete, instead of "
             "visiting each one to find out",
    )
    parser.add_argument(
        "--force", action="store_true", default=default,
        help="ignore the index and fetch everything again, overwriting what is "
             "already on disk. Use after changing what gets saved",
    )
    parser.add_argument(
        "--nested", action="store_true", default=default,
        help="give each post its own folder. The default is flat: every file "
             "sits in the account folder, named <date>_<postid>_NN",
    )
    # Flat is the default now, so this is a no-op. Kept so that typing what the
    # flag used to be called is not an error.
    parser.add_argument(
        "--flatten", action="store_true", default=default,
        help=argparse.SUPPRESS,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instagram-archiver",
        description="Archive Instagram photos and videos your account can already see.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    _common_options(parser, default=None)

    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="open a window and wait for manual login")
    _common_options(login, default=argparse.SUPPRESS)
    login.set_defaults(url=None, max_posts=None)

    profile = sub.add_parser("profile", help="archive every visible post on a profile")
    _common_options(profile, default=argparse.SUPPRESS)
    profile.add_argument("url", help="profile URL")
    profile.add_argument(
        "--max-posts", type=int, default=None,
        help="stop after N posts (useful for a first test run)",
    )

    rearrange = sub.add_parser(
        "relayout",
        help="rearrange an archive already on disk; no browser, no network",
    )
    _common_options(rearrange, default=argparse.SUPPRESS)
    rearrange.add_argument(
        "--dry-run", action="store_true",
        help="list what would move, without moving anything",
    )
    rearrange.set_defaults(url=None, max_posts=None)

    fill = sub.add_parser(
        "fill-videos",
        help="fetch only the videos an earlier run skipped, using the index",
    )
    _common_options(fill, default=argparse.SUPPRESS)
    fill.set_defaults(url=None, max_posts=None)

    post = sub.add_parser("post", help="archive one specific post URL")
    _common_options(post, default=argparse.SUPPRESS)
    post.add_argument("url", help="post or reel URL")
    post.set_defaults(max_posts=None)

    return parser


# A flag registered both before and after the subcommand parses twice, and the
# subcommand pass must not reset a value given before it. None means "not
# supplied here"; these are the values to fall back to when it appears nowhere.
FLAG_DEFAULTS = {
    "out": None,
    "browser_profile": None,
    "headless": False,
    "skip_videos": False,
    "videos": False,
    "include_reels": False,
    "flatten": False,
    "nested": False,
    "force": False,
    "resume": False,
    "log": None,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and normalise, so flag position never changes the result."""
    args = build_parser().parse_args(argv)
    for name, fallback in FLAG_DEFAULTS.items():
        if getattr(args, name, None) is None:
            setattr(args, name, fallback)
    # A flat account folder is the layout; --nested asks for the old one.
    # `flatten` stays the internal name because that is what it controls.
    args.flatten = not args.nested
    return args


def print_summary(summary: Summary, out_dir: Path) -> None:
    print()
    print("=" * 50)
    print(f"Posts visited        : {summary.posts_visited}")
    print(f"Posts yielding media : {summary.posts_with_media}")
    downloaded = summary.images + summary.videos - summary.moved
    print(f"Files downloaded     : {max(downloaded, 0)}")
    if summary.moved:
        print(f"Files moved          : {summary.moved} (already had them)")
    print(f"Images               : {summary.images}")
    print(f"Videos downloaded    : {summary.videos}")
    if summary.skipped_videos:
        print(f"Videos not saved     : {summary.skipped_videos} "
              f"(placeholder images written)")
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
    args = parse_args(argv)

    out_dir = (args.out or default_output_dir()).resolve()
    profile_dir = (args.browser_profile or default_browser_profile_dir()).resolve()
    headless = args.headless and args.command != "login"
    # Photographs are the product. Videos are opt-in until they can be
    # attributed reliably; a video slide leaves a placeholder either way.
    want_videos = args.videos


    # --force starts with an empty memory, so nothing is treated as already had.
    if str(args.log) != "-":
        log_path = args.log or (out_dir / logfile.DEFAULT_NAME)
        logfile.start(log_path)
        print(f"logging to {log_path}")

    if args.command == "relayout":
        wanted = "flat" if args.flatten else "one folder per post"
        print(f"Rearranging {out_dir} to: {wanted}")
        moved, skipped = relayout.apply(out_dir, args.flatten,
                                        dry_run=getattr(args, "dry_run", False))
        emptied, stuck = prune_empty_dirs(out_dir)
        print()
        print("=" * 50)
        print(f"Files moved   : {moved}")
        if skipped:
            print(f"Left alone    : {skipped} (something was already in the way)")
        if emptied:
            print(f"Folders tidied: {emptied}")
        if stuck:
            print(f"Left behind   : {stuck} empty folder(s); permission denied.")
            print("                A sync client such as OneDrive holds folders")
            print("                it is watching. They can be deleted by hand.")
        print(f"Archive       : {out_dir}")
        print("=" * 50)
        return 0

    hashes = set() if args.force else load_known_hashes(out_dir)
    # Where the files we already hold are sitting, so a layout change moves
    # them rather than downloading everything a second time.
    archived = {} if args.force else load_archived_files(out_dir)
    if args.force:
        print("--force: ignoring the index, everything will be fetched again.")
        print("")

    summary = Summary()

    try:
        with browser_session(profile_dir, headless=headless) as (context, page):
            ensure_login(context, page)

            if args.command == "login":
                print("Login step complete - nothing downloaded.")
                return 0

            try:
                if args.command == "fill-videos":
                    targets = posts_missing_videos(out_dir)
                    if not targets:
                        print("Nothing to fill in: no placeholders in the index.")
                        return 0
                    print(f"{len(targets)} post(s) hold a placeholder where a "
                          f"video should be.")
                    started = time.time()
                    for i, post_url in enumerate(targets, start=1):
                        print(f"[{i}/{len(targets)}]", end=" ")
                        records = save_post(
                            context, page, post_url, out_dir, hashes,
                            True, None, args.flatten, archived,
                        )
                        summary.records += records
                        summary.posts_visited += 1
                        write_index(out_dir, records)
                        print(progress_line(i, len(targets),
                                            len(summary.records), started),
                              flush=True)
                        if i < len(targets):
                            nap(POST_PAUSE)
                elif args.command == "post":
                    post_url = normalise_post_url(args.url)
                    if not post_url:
                        print(f"Not an Instagram post/reel URL: {args.url}", file=sys.stderr)
                        return 2
                    summary = archive_post(
                        context, page, post_url, out_dir, hashes,
                        want_videos, args.flatten, archived,
                    )
                else:
                    summary = archive_profile(
                        context, page, args.url, out_dir, hashes,
                        want_videos, args.max_posts, args.flatten,
                        args.include_reels, archived, args.resume,
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
