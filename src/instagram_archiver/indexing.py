"""The CSV/JSON records describing what was saved.

Each account keeps its own records under `<account>/metadata/`, beside its
media rather than mixed in with it. The index doubles as the deduplication
memory: hashes are loaded before a run so files already on disk are never
fetched twice.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .media import MediaRecord
from .paths import METADATA_DIR, account_dir_name, metadata_dir

PLACEHOLDER_TYPE = "video_skipped"

# Excel and PowerShell 5.1 read a CSV as the legacy Windows codepage unless it
# starts with a byte-order mark, which turns Icelandic and every other
# non-ASCII caption into mojibake. utf-8-sig writes the mark; the content is
# ordinary UTF-8 either way.
CSV_ENCODING = "utf-8-sig"

INDEX_JSON = "index.json"
INDEX_CSV = "index.csv"
COMMENTS_JSON = "comments.json"
COMMENTS_CSV = "comments.csv"

COMMENT_FIELDS = ["post_url", "post_id", "post_date", "account", "username",
                  "timestamp", "text"]


# --------------------------------------------------------------- reading ---

def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def index_paths(out_dir: Path) -> list[Path]:
    """Every account's index under this archive."""
    return sorted(out_dir.glob(f"*/{METADATA_DIR}/{INDEX_JSON}"))


def _read_existing(out_dir: Path) -> list[dict]:
    """Every row, across every account in this archive."""
    rows: list[dict] = []
    for path in index_paths(out_dir):
        rows.extend(_read_json(path))
    return rows


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


# --------------------------------------------------------------- writing ---

def _write_pair(meta_dir: Path, stem_json: str, stem_csv: str,
                rows: list[dict], fields: list[str] | None = None) -> None:
    """Write one set of rows as both JSON and CSV."""
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / stem_json).write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if fields is None:
        # Rows written by an older version may lack newer columns; take the
        # union so an upgrade never drops data or crashes the writer.
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    if not fields:
        return

    with (meta_dir / stem_csv).open("w", newline="", encoding=CSV_ENCODING) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, restval="",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_index_rows(out_dir: Path, rows: list[dict]) -> None:
    """Rewrite the indexes from raw rows, e.g. after a layout change."""
    by_account: dict[str, list[dict]] = {}
    for row in rows:
        by_account.setdefault(row.get("username") or "unknown-account",
                              []).append(row)
    for username, group in by_account.items():
        _write_pair(metadata_dir(out_dir, username), INDEX_JSON, INDEX_CSV, group)


def write_index(out_dir: Path, records: list[MediaRecord]) -> None:
    """Merge new records into each account's index."""
    if not records:
        return

    by_account: dict[str, list[MediaRecord]] = {}
    for record in records:
        by_account.setdefault(record.username, []).append(record)

    for username, group in by_account.items():
        meta_dir = metadata_dir(out_dir, username)
        existing = _read_json(meta_dir / INDEX_JSON)

        # Positions where this batch saved real media: any placeholder standing
        # in for them is now history and must not linger.
        filled = {
            (r.post_id, r.carousel_index)
            for r in group
            if r.media_type != PLACEHOLDER_TYPE
        }

        # Keyed so a new record supersedes an older one for the same content:
        # a file that moved needs its recorded path updated, not a second row.
        merged: dict[tuple, dict] = {}
        for row in existing:
            if (row.get("media_type") == PLACEHOLDER_TYPE
                    and (row.get("post_id"), row.get("carousel_index")) in filled):
                continue
            merged[(row.get("post_id"), row.get("sha256"),
                    row.get("carousel_index"))] = row

        for record in group:
            row = asdict(record)
            row.pop("relocated", None)      # run details, not archive data
            row.pop("refreshed", None)
            merged[(record.post_id, record.sha256, record.carousel_index)] = row

        _write_pair(meta_dir, INDEX_JSON, INDEX_CSV, list(merged.values()))


def write_comments(out_dir: Path, rows: list[dict]) -> int:
    """Merge comment rows into each account's comment files.

    Kept apart from the media index: comments are other people's words about
    the post, not a description of a file on disk. Returns how many were new.
    """
    if not rows:
        return 0

    by_account: dict[str, list[dict]] = {}
    for row in rows:
        by_account.setdefault(row.get("account") or "unknown-account",
                              []).append(row)

    added_total = 0
    for account, group in by_account.items():
        meta_dir = out_dir / account_dir_name(account) / METADATA_DIR
        existing = _read_json(meta_dir / COMMENTS_JSON)
        seen = {
            (r.get("post_id"), r.get("username"), r.get("timestamp"), r.get("text"))
            for r in existing
        }

        added = []
        for row in group:
            key = (row.get("post_id"), row.get("username"),
                   row.get("timestamp"), row.get("text"))
            if key in seen:
                continue
            seen.add(key)
            added.append(row)

        if added:
            _write_pair(meta_dir, COMMENTS_JSON, COMMENTS_CSV,
                        existing + added, COMMENT_FIELDS)
            added_total += len(added)

    return added_total
