"""The CSV/JSON index that records what was saved.

The index doubles as the deduplication memory: hashes are loaded before a run
so files already on disk are never fetched twice.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .media import MediaRecord

PLACEHOLDER_TYPE = "video_skipped"

INDEX_JSON = "index.json"
INDEX_CSV = "index.csv"
COMMENTS_JSON = "comments.json"
COMMENTS_CSV = "comments.csv"

COMMENT_FIELDS = ["post_url", "post_id", "post_date", "username",
                 "timestamp", "text"]


def _read_existing(out_dir: Path) -> list[dict]:
    path = out_dir / INDEX_JSON
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def load_known_hashes(out_dir: Path) -> set[str]:
    return {row["sha256"] for row in _read_existing(out_dir) if row.get("sha256")}


def load_archived_files(out_dir: Path) -> dict[tuple[str, int], Path]:
    """Where each already-saved item currently lives, keyed by post and position.

    Lets a run that changes the output layout move files it already has rather
    than downloading them a second time.
    """
    found: dict[tuple[str, int], Path] = {}
    for row in _read_existing(out_dir):
        try:
            key = (row["post_id"], int(row["carousel_index"]))
            path = out_dir / Path(row["relative_path"])
        except (KeyError, TypeError, ValueError):
            continue
        if path.is_file():
            found[key] = path
    return found


def posts_missing_videos(out_dir: Path) -> list[str]:
    """Post URLs that hold a placeholder where a video should be.

    The index already knows which slides were skipped, so filling them in does
    not need the profile walked again - only those posts revisited.
    """
    urls: list[str] = []
    seen: set[str] = set()
    for row in _read_existing(out_dir):
        if row.get("media_type") != PLACEHOLDER_TYPE:
            continue
        url = row.get("post_url")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def completed_post_ids(out_dir: Path, want_videos: bool) -> set[str]:
    """Posts with nothing left to fetch, so a resumed run can skip them.

    A post counts as done when the index holds rows for it and, when videos
    are wanted, none of those rows is still a placeholder. Instagram posts do
    not change after publication, so this is safe to trust.
    """
    rows_by_post: dict[str, list[dict]] = {}
    for row in _read_existing(out_dir):
        post_id = row.get("post_id")
        if post_id:
            rows_by_post.setdefault(post_id, []).append(row)

    done = set()
    for post_id, rows in rows_by_post.items():
        if want_videos and any(r.get("media_type") == PLACEHOLDER_TYPE for r in rows):
            continue
        done.add(post_id)
    return done


def write_index_rows(out_dir: Path, rows: list[dict]) -> None:
    """Write both index files from raw rows, e.g. after a layout change."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / INDEX_JSON).write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        return
    with (out_dir / INDEX_CSV).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, restval="", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_index(out_dir: Path, records: list[MediaRecord]) -> None:
    """Merge new records into the index, then rewrite both files."""
    if not records:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    # Keyed so a new record supersedes an older one for the same content:
    # a file that moved needs its recorded path updated, not a second row.
    # Positions where this batch saved real media: any placeholder standing in
    # for them is now history and must not linger in the index.
    filled = {
        (r.post_id, r.carousel_index)
        for r in records
        if r.media_type != PLACEHOLDER_TYPE
    }

    merged_by_key: dict[tuple, dict] = {}
    for row in _read_existing(out_dir):
        if (row.get("media_type") == PLACEHOLDER_TYPE
                and (row.get("post_id"), row.get("carousel_index")) in filled):
            continue
        merged_by_key[(row.get("post_id"), row.get("sha256"),
                       row.get("carousel_index"))] = row
    for record in records:
        row = asdict(record)
        row.pop("relocated", None)      # a run detail, not archive data
        row.pop("refreshed", None)
        merged_by_key[(record.post_id, record.sha256,
                       record.carousel_index)] = row
    merged = list(merged_by_key.values())

    (out_dir / INDEX_JSON).write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Rows written by an older version may lack newer columns; take the union
    # so an upgrade never drops data or crashes the writer.
    fields: list[str] = []
    for row in merged:
        for key in row:
            if key not in fields:
                fields.append(key)

    with (out_dir / INDEX_CSV).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, restval="", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(merged)


def _read_comments(out_dir: Path) -> list[dict]:
    path = out_dir / COMMENTS_JSON
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def write_comments(out_dir: Path, rows: list[dict]) -> int:
    """Merge comment rows into comments.json / comments.csv.

    Kept apart from the media index: comments are other people's words about
    the post, not a description of a file on disk. Returns how many were new.
    """
    if not rows:
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    existing = _read_comments(out_dir)
    seen = {
        (r.get("post_id"), r.get("username"), r.get("timestamp"), r.get("text"))
        for r in existing
    }

    added = []
    for row in rows:
        key = (row.get("post_id"), row.get("username"), row.get("timestamp"),
               row.get("text"))
        if key in seen:
            continue
        seen.add(key)
        added.append(row)

    if not added:
        return 0

    merged = existing + added
    (out_dir / COMMENTS_JSON).write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (out_dir / COMMENTS_CSV).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMENT_FIELDS, restval="",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    return len(added)
