"""Rearranging an archive that is already on disk.

Changing layout is a local file operation. The index records where every item
lives and what it belongs to, which is everything needed to work out where it
should live instead - so this never opens a browser and never touches
Instagram.
"""

from __future__ import annotations

from pathlib import Path

from .indexing import _read_existing, write_index_rows
from .paths import account_dir_name
from .placeholder import SUFFIX as PLACEHOLDER_SUFFIX

REELS_DIR_NAME = "reels"


def _tail(filename: str, stem: str) -> str:
    """The part of a filename after any `<date>_<postid>_` prefix."""
    prefix = f"{stem}_"
    return filename[len(prefix):] if filename.startswith(prefix) else filename


def desired_path(out_dir: Path, row: dict, flatten: bool) -> Path | None:
    """Where this item belongs under the requested layout."""
    try:
        username = row["username"]
        post_id = row["post_id"]
        post_date = row["post_date"]
        filename = row["filename"]
    except KeyError:
        return None

    root = out_dir / account_dir_name(username)
    if "/reel/" in (row.get("post_url") or ""):
        root = root / REELS_DIR_NAME

    stem = f"{post_date}_{post_id}"
    tail = _tail(filename, stem)
    return root / f"{stem}_{tail}" if flatten else root / stem / tail


def plan(out_dir: Path, flatten: bool) -> list[tuple[dict, Path, Path]]:
    """Rows whose file exists and is not already where it should be."""
    moves = []
    for row in _read_existing(out_dir):
        rel = row.get("relative_path")
        if not rel:
            continue
        current = out_dir / Path(rel)
        target = desired_path(out_dir, row, flatten)
        if target is None or target == current:
            continue
        if current.is_file():
            moves.append((row, current, target))
    return moves


def apply(out_dir: Path, flatten: bool, dry_run: bool = False) -> tuple[int, int]:
    """Move everything into the requested layout. Returns (moved, skipped)."""
    rows = _read_existing(out_dir)
    by_rel = {row.get("relative_path"): row for row in rows}

    moved = 0
    skipped = 0
    for row, current, target in plan(out_dir, flatten):
        if target.exists():
            # Something is already sitting there; leave both alone rather than
            # overwriting a file we cannot prove is the same one.
            print(f"  ! {target.name} already exists, leaving {current.name} alone")
            skipped += 1
            continue
        if dry_run:
            print(f"  would move {current.name} -> {target.relative_to(out_dir).as_posix()}")
            moved += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        current.replace(target)

        stored = by_rel.get(row.get("relative_path"))
        if stored is not None:
            stored["filename"] = target.name
            stored["relative_path"] = target.relative_to(out_dir).as_posix()
        moved += 1

    if moved and not dry_run:
        write_index_rows(out_dir, rows)

    return moved, skipped


__all__ = ["apply", "desired_path", "plan", "PLACEHOLDER_SUFFIX"]
