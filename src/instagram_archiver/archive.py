"""Turning a post into files on disk."""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from dataclasses import dataclass, field

from . import placeholder
from .config import MIN_IMAGE_BYTES, POST_PAUSE
from .indexing import write_index
from .media import MediaRecord, fetch, resolve_video
from .paths import account_dir_name
from .progress import line as progress_line
from .scraper import collect_post_media, enumerate_profile_posts, nap
from .urls import image_extension, post_id_from, username_from_profile_url

WORK_DIR_NAME = ".work"


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
    def skipped_videos(self) -> int:
        return sum(1 for r in self.records if r.media_type == "video_skipped")

    @property
    def posts_with_media(self) -> int:
        return len({r.post_id for r in self.records})


def save_post(context, page, sniffer, post_url, out_dir, hashes, want_videos=True,
              username_hint=None, flatten=False):
    """Download every photo and video in one post. Returns its MediaRecords."""
    post_id = post_id_from(post_url)
    print(f"- {post_url}")

    meta, items = collect_post_media(
        page, sniffer, post_url, want_videos, username_hint=username_hint
    )
    if not items:
        return []

    post_date, username = meta.date, meta.username

    # One folder per account, so archiving several accounts stays tidy.
    # --flatten drops the per-post folder and prefixes the filename instead.
    account_dir = account_dir_name(username)
    stem = f"{post_date}_{post_id}"
    folder = out_dir / account_dir if flatten else out_dir / account_dir / stem
    prefix = f"{stem}_" if flatten else ""
    work_dir = out_dir / account_dir / WORK_DIR_NAME
    records: list[MediaRecord] = []

    def file_placeholder(position):
        """Mark a video we deliberately did not download."""
        filename = f"{prefix}{position:02d}{placeholder.SUFFIX}"
        dest = folder / filename
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
        print(f"  . {account_dir}/{folder.name}/{filename}  (video not saved)")

    def file_it(position, local_path, source_url, media_type, extension, note=""):
        """File one item under its position in the post."""
        filename = f"{prefix}{position:02d}{extension}"
        dest = folder / filename

        if local_path is None:                          # image: fetch it now
            digest = fetch(context, source_url, dest, MIN_IMAGE_BYTES)
            if digest is None:
                return
        else:                                           # video: already local
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(local_path), str(dest))
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()

        if digest in hashes:                            # already in the library
            dest.unlink(missing_ok=True)
            print(f"  = already have {filename}")
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


def archive_post(context, page, sniffer, post_url, out_dir, hashes, want_videos=True,
                 flatten=False):
    summary = Summary()
    records = save_post(
        context, page, sniffer, post_url, out_dir, hashes, want_videos, flatten=flatten
    )
    summary.records += records
    summary.posts_visited = 1
    write_index(out_dir, records)
    return summary


def archive_profile(
    context, page, sniffer, profile_url, out_dir, hashes,
    want_videos=True, max_posts=None, flatten=False, include_reels=False,
):
    summary = Summary()
    targets = enumerate_profile_posts(page, profile_url, max_posts, include_reels)
    started = time.time()
    # The profile URL names the account, which beats guessing from each page.
    hint = username_from_profile_url(profile_url)

    for i, post_url in enumerate(targets, start=1):
        print(f"[{i}/{len(targets)}]", end=" ")
        records = save_post(
            context, page, sniffer, post_url, out_dir, hashes, want_videos, hint, flatten
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

    return summary
