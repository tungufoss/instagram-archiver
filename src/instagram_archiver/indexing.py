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
    return {row["sha256"] for row in _read_existing(out_dir) if "sha256" in row}


def write_index(out_dir: Path, records: list[MediaRecord]) -> None:
    """Merge new records into the index, then rewrite both files."""
    if not records:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    existing = _read_existing(out_dir)
    known = {(row.get("post_id"), row.get("sha256")) for row in existing}
    merged = existing + [
        asdict(record)
        for record in records
        if (record.post_id, record.sha256) not in known
    ]

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
