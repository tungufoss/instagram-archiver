"""Post-level metadata: what a profile posted, when, and how it did.

The media index describes files on disk, one row per file. This is one row per
post, and it can be gathered without downloading anything - the page carries
the counts and the media list already.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import account_dir_name

POSTS_JSON = "posts.json"
POSTS_CSV = "posts.csv"


@dataclass
class PostRecord:
    """One post, described rather than downloaded."""

    post_url: str
    post_id: str
    username: str
    post_date: str
    post_time: str          # exact ISO timestamp when the page gave one
    kind: str               # "post" or "reel"
    likes: int
    views: int | None
    comments: int
    images: int
    videos: int
    media_count: int
    caption: str


def account_dir(out_dir: Path, username: str) -> Path:
    """Post metadata lives with that account's media, not at the archive root.

    Scanning two accounts should give two files, not one mixed together.
    """
    return out_dir / account_dir_name(username or "unknown-account")


def _read(out_dir: Path) -> list[dict]:
    path = out_dir / POSTS_JSON
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def write_posts(out_dir: Path, records: list[PostRecord]) -> list[Path]:
    """Merge post rows into each account's posts.json / posts.csv.

    Returns the directories written to.
    """
    if not records:
        return []

    by_account: dict[str, list[PostRecord]] = {}
    for record in records:
        by_account.setdefault(record.username, []).append(record)

    written = []
    for username, group in by_account.items():
        written.append(_write_one(account_dir(out_dir, username), group))
    return written


def _write_one(out_dir: Path, records: list[PostRecord]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {row.get("post_id"): row for row in _read(out_dir)}
    for record in records:
        by_id[record.post_id] = asdict(record)

    # Newest first: a profile reads more naturally in reverse chronology.
    merged = sorted(
        by_id.values(),
        key=lambda r: (r.get("post_time") or r.get("post_date") or ""),
        reverse=True,
    )

    (out_dir / POSTS_JSON).write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    fields = list(asdict(records[0]).keys())
    for row in merged:
        for key in row:
            if key not in fields:
                fields.append(key)

    with (out_dir / POSTS_CSV).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, restval="",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)

    return out_dir


def summarise(records: list[PostRecord]) -> dict:
    """Totals worth printing at the end of a scan."""
    return {
        "posts": len(records),
        "reels": sum(1 for r in records if r.kind == "reel"),
        "images": sum(r.images for r in records),
        "videos": sum(r.videos for r in records),
        "likes": sum(r.likes for r in records),
        "views": (sum(r.views for r in records if r.views is not None)
                  if any(r.views is not None for r in records) else "not shown"),
        "comments": sum(r.comments for r in records),
        "with_caption": sum(1 for r in records if r.caption),
    }
