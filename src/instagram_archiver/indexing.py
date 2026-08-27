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

INDEX_JSON = "index.json"
INDEX_CSV = "index.csv"


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


def write_index(out_dir: Path, records: list[MediaRecord]) -> None:
    """Merge new records into the index, then rewrite both files."""
    if not records:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    # Keyed so a new record supersedes an older one for the same content:
    # a file that moved needs its recorded path updated, not a second row.
    merged_by_key: dict[tuple, dict] = {}
    for row in _read_existing(out_dir):
        merged_by_key[(row.get("post_id"), row.get("sha256"),
                       row.get("carousel_index"))] = row
    for record in records:
        row = asdict(record)
        row.pop("relocated", None)      # a run detail, not archive data
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
