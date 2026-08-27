"""Turning a post into files on disk."""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import placeholder
from .config import MIN_IMAGE_BYTES, POST_PAUSE
from .indexing import completed_post_ids, write_index
from .media import MediaRecord, fetch, resolve_video
from .paths import account_dir_name
from .progress import line as progress_line
from .scraper import collect_post_media, enumerate_profile_posts, nap
from .urls import image_extension, post_id_from, username_from_profile_url

WORK_DIR_NAME = ".work"
REELS_DIR_NAME = "reels"


def already_archived(dest: Path, hashes: set[str]) -> bool:
    """True when `dest` already holds bytes this archive has recorded.

    The destination is not a scratch area. A file sitting in the right place
    with content we know about is the finished article: it must not be fetched
    over and must not be deleted. Getting this wrong once emptied a verified
    folder of nine photographs, leaving only placeholders behind.
    """
    try:
        if not dest.is_file():
            return False
        return hashlib.sha256(dest.read_bytes()).hexdigest() in hashes
    except OSError:
        return False


@dataclass
class Summary:
    posts_visited: int = 0
    records: list[MediaRecord] = field(default_factory=list)

    @property
    def images(self) -> int:
        return sum(1 for r in self.records if r.media_type == "image")

    @property
    def videos(self) -> int:
        return sum(1 for r in self.records if r.media_type == "video")

    @property
    def moved(self) -> int:
        return sum(1 for r in self.records if r.relocated)

    @property
    def skipped_videos(self) -> int:
        return sum(1 for r in self.records if r.media_type == "video_skipped")

    @property
    def posts_with_media(self) -> int:
        return len({r.post_id for r in self.records})


def save_post(context, page, post_url, out_dir, hashes, want_videos=True,
              username_hint=None, flatten=False, archived=None):
    """Download every photo and video in one post. Returns its MediaRecords."""
    post_id = post_id_from(post_url)
    print(f"- {post_url}")

    meta, items = collect_post_media(
        page, post_url, want_videos, username_hint=username_hint
    )
    if not items:
        return []

    post_date, username = meta.date, meta.username

    # One folder per account, so archiving several accounts stays tidy.
    # Reels go in their own subfolder: they carry no photographs, so keeping
    # them apart leaves the photo archive as a photo archive.
    account_dir = account_dir_name(username)
    root = out_dir / account_dir
    if "/reel/" in post_url:
        root = root / REELS_DIR_NAME

    # --flatten drops the per-post folder and prefixes the filename instead.
    stem = f"{post_date}_{post_id}"
    folder = root if flatten else root / stem
    prefix = f"{stem}_" if flatten else ""
    work_dir = root / WORK_DIR_NAME
    records: list[MediaRecord] = []

    def file_placeholder(position):
        """Mark a video we deliberately did not download."""
        filename = f"{prefix}{position:02d}{placeholder.SUFFIX}"
        dest = folder / filename

        # A placeholder is cheap to recreate, but moving the existing one keeps
        # its timestamp and avoids churning the file on every layout change.
        held = (archived or {}).get((post_id, position))
        reusable = (
            held is not None
            and held != dest
            and held.is_file()
            and held.name.endswith(placeholder.SUFFIX)
        )
        if reusable:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(held), str(dest))
        else:
            placeholder.write(dest)
        if meta.timestamp is not None:
            try:
                os.utime(dest, (meta.timestamp, meta.timestamp))
            except OSError:
                pass
        records.append(
            MediaRecord(
                post_url=post_url,
                username=username,
                post_id=post_id,
                post_date=post_date,
                media_type="video_skipped",
                carousel_index=position,
                filename=filename,
                relative_path=str(dest.relative_to(out_dir)).replace("\\", "/"),
                source_url="",
                sha256="",
            )
        )
        shown = dest.relative_to(out_dir).as_posix()
        print(f"  . {shown}  (video not saved)")

    def file_it(position, local_path, source_url, media_type, extension, note=""):
        """File one item under its position in the post."""
        filename = f"{prefix}{position:02d}{extension}"
        dest = folder / filename

        # A file already sitting in the right place is the finished article.
        # Never fetch over it and never delete it: the destination is not a
        # scratch area, and treating it as one destroyed real archives.
        existed = dest.exists()
        if already_archived(dest, hashes):
            print(f"  = already have {filename}")
            return

        # We may already hold these bytes somewhere else in the archive - the
        # usual case being a layout change such as --flatten. Moving beats
        # downloading a copy of what is already on the disk.
        held = (archived or {}).get((post_id, position))
        if held is not None and held != dest and held.is_file():
            if held.suffix == dest.suffix:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(held), str(dest))
                digest = hashlib.sha256(dest.read_bytes()).hexdigest()
                hashes.add(digest)
                records.append(
                    MediaRecord(
                        post_url=post_url, username=username, post_id=post_id,
                        post_date=post_date, media_type=media_type,
                        carousel_index=position, filename=filename,
                        relative_path=str(dest.relative_to(out_dir)).replace("\\", "/"),
                        source_url=source_url,
                        sha256=digest,
                        relocated=True,
                    )
                )
                print(f"  > moved {held.name} -> {dest.relative_to(out_dir).as_posix()}")
                return

        if local_path is None:                          # image: fetch it now
            digest = fetch(context, source_url, dest, MIN_IMAGE_BYTES)
            if digest is None:
                return
        else:                                           # video: already local
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(local_path), str(dest))
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()

        if digest in hashes:
            # These bytes are already stored under some other post. Drop the
            # copy we just made, but only if we created the file ourselves.
            if not existed:
                dest.unlink(missing_ok=True)
            print(f"  = duplicate of a file already archived ({filename})")
            return

        # Stamp the file with when the post was made, not when we fetched it,
        # so the archive sorts by date in any file browser. Instagram strips
        # EXIF from uploads, so the filesystem time is the honest place for it.
        if meta.timestamp is not None:
            try:
                os.utime(dest, (meta.timestamp, meta.timestamp))
            except OSError:
                pass

        hashes.add(digest)
        if not note:
            note = f"({dest.stat().st_size / 1024:.0f} KB)"
        records.append(
            MediaRecord(
                post_url=post_url,
                username=username,
                post_id=post_id,
                post_date=post_date,
                media_type=media_type,
                carousel_index=position,
                filename=filename,
                relative_path=str(dest.relative_to(out_dir)).replace("\\", "/"),
                source_url=source_url,
                sha256=digest,
            )
        )
        # A placeholder only ever stood in for this file. Now that the real
        # thing is here, it would just be a confusing duplicate.
        if media_type != "video_skipped":
            stale = folder / f"{prefix}{position:02d}{placeholder.SUFFIX}"
            if stale.exists():
                try:
                    stale.unlink()
                    print(f"    (replaced {stale.name})")
                except OSError:
                    pass

        shown = dest.relative_to(out_dir).as_posix()
        print(f"  + {shown}  {note}")

    try:
        # The index is the slide's position in the post, so a file keeps the
        # same number no matter what a given run happens to download.
        for position, item in enumerate(items, start=1):
            if item["kind"] == "video_skipped":
                file_placeholder(position)
            elif item["kind"] == "image":
                file_it(position, None, item["url"], "image",
                        image_extension(item["url"]))
            else:
                for path, source_url in resolve_video(context, item["urls"], work_dir):
                    size_mb = path.stat().st_size / 1_048_576
                    file_it(position, path, source_url, "video", ".mp4",
                            f"(video, {size_mb:.1f} MB)")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return records


def prune_empty_dirs(root: Path) -> tuple[int, int]:
    """Remove directories a layout change has emptied.

    Returns (removed, could_not_remove). The second number matters on Windows,
    where a sync client such as OneDrive keeps handles on folders it is
    watching and rmdir fails with a permission error. Failing silently there
    left dozens of empty folders behind with nothing to explain them.

    Deepest first, so a folder emptied by its children is caught in one pass.
    """
    removed = 0
    stuck = 0
    if not root.is_dir():
        return removed, stuck
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            try:
                path.rmdir()
                removed += 1
            except OSError:
                stuck += 1
    return removed, stuck


def archive_post(context, page, post_url, out_dir, hashes, want_videos=True,
                 flatten=False, archived=None):
    summary = Summary()
    records = save_post(
        context, page, post_url, out_dir, hashes, want_videos,
        flatten=flatten, archived=archived,
    )
    summary.records += records
    summary.posts_visited = 1
    write_index(out_dir, records)
    prune_empty_dirs(out_dir)
    return summary


def archive_profile(
    context, page, profile_url, out_dir, hashes,
    want_videos=True, max_posts=None, flatten=False, include_reels=False,
    archived=None, resume=False,
):
    summary = Summary()
    skipped_reels: list[str] = []
    targets = enumerate_profile_posts(
        page, profile_url, max_posts, include_reels, skipped_reels
    )
    if skipped_reels:
        # Written down rather than merely mentioned, so nothing leaves the
        # archive without a trace of what it was.
        note = out_dir / "skipped-reels.txt"
        note.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "Reels not archived by this run.",
            "Re-run with --include-reels to fetch them.",
            "",
            *skipped_reels,
            "",
        ]
        note.write_text("\n".join(lines), encoding="utf-8")
        print(f"  listed them in {note.name}")
    if resume:
        done = completed_post_ids(out_dir, want_videos)
        before = len(targets)
        targets = [u for u in targets if post_id_from(u) not in done]
        skipped = before - len(targets)
        if skipped:
            print(f"  resuming: {skipped} post(s) already complete, "
                  f"{len(targets)} to do")
        if not targets:
            print("  nothing left to fetch.")

    started = time.time()
    # The profile URL names the account, which beats guessing from each page.
    hint = username_from_profile_url(profile_url)

    for i, post_url in enumerate(targets, start=1):
        print(f"[{i}/{len(targets)}]", end=" ")
        records = save_post(
            context, page, post_url, out_dir, hashes, want_videos, hint,
            flatten, archived,
        )
        summary.records += records
        summary.posts_visited += 1
        # Written per post, not at the end: an interrupted run must not lose
        # the record of what it already fetched, or a re-run repeats the work.
        write_index(out_dir, records)
        print(progress_line(i, len(targets), len(summary.records), started),
              flush=True)
        if i < len(targets):
            nap(POST_PAUSE)

    emptied, stuck = prune_empty_dirs(out_dir)
    if emptied:
        print(f"  tidied {emptied} empty folder(s) left by the layout change")
    if stuck:
        print(f"  ! {stuck} empty folder(s) could not be removed (permission "
              f"denied - a sync client such as OneDrive may be holding them)")

    return summary
