"""Who follows an account, and how that changes over time.

Each run writes a dated snapshot of the usernames and appends a row to a
timeseries, so a later run can say who arrived and who left. Only what the
profile shows you is read; there is no way here to see a list you could not
open yourself.

A follower list for a private family or class account is sensitive - it is a
list of real people, often parents and children. It is written to your own
disk and nowhere else, and it is worth keeping that way.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .indexing import CSV_ENCODING
from .paths import account_dir_name

SNAPSHOT_DIR = "followers"
TIMESERIES_CSV = "followers.csv"
TIMESERIES_FIELDS = ["taken_at", "count", "stated_count", "complete",
                     "joined", "left"]


@dataclass
class Change:
    """What moved between two snapshots."""

    joined: list[str]
    left: list[str]
    reliable: bool = True

    @property
    def quiet(self) -> bool:
        return not self.joined and not self.left


def account_dir_for(out_dir: Path, username: str) -> Path:
    """Follower history lives with that account's other records."""
    return out_dir / account_dir_name(username or "unknown-account")


def snapshot_path(account_dir: Path, taken_at: datetime) -> Path:
    return account_dir / SNAPSHOT_DIR / f"{taken_at:%Y-%m-%d_%H%M}.json"


def previous_snapshot(account_dir: Path) -> tuple[list[str], bool]:
    """Usernames from the most recent snapshot, and whether it was complete."""
    folder = account_dir / SNAPSHOT_DIR
    if not folder.is_dir():
        return [], True
    files = sorted(folder.glob("*.json"))
    if not files:
        return [], True
    try:
        data = json.loads(files[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], True
    if not isinstance(data, dict):
        return (data if isinstance(data, list) else []), True
    usernames = data.get("followers")
    return (usernames if isinstance(usernames, list) else [],
            bool(data.get("complete", True)))


def compare(before: list[str], after: list[str], reliable: bool = True) -> Change:
    """Who is new, and who has gone.

    `reliable` is False when either snapshot is known to be partial. The
    comparison is still made, but "left" then means "not seen this time",
    which is a very different claim from "stopped following".
    """
    was, now = set(before), set(after)
    return Change(joined=sorted(now - was), left=sorted(was - now),
                  reliable=reliable)


def write_snapshot(account_dir: Path, username: str, followers: list[str],
                   taken_at: datetime | None = None,
                   stated: int | None = None) -> tuple[Path, Change]:
    """Record this snapshot and report what changed since the last one."""
    taken_at = taken_at or datetime.now(timezone.utc)
    complete = stated is None or len(followers) >= stated

    before, before_complete = previous_snapshot(account_dir)
    change = compare(before, followers, reliable=complete and before_complete)

    path = snapshot_path(account_dir, taken_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "account": username,
                "taken_at": taken_at.isoformat(timespec="seconds"),
                "count": len(followers),
                # What the profile claimed, and whether we matched it. A
                # partial snapshot must not be read as the full membership.
                "stated_count": stated,
                "complete": complete,
                "followers": sorted(followers),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _append_timeseries(account_dir, taken_at, len(followers), change, stated,
                       complete)
    return path, change


def _append_timeseries(account_dir: Path, taken_at: datetime, count: int,
                       change: Change, stated: int | None,
                       complete: bool) -> None:
    path = account_dir / TIMESERIES_CSV
    exists = path.exists()
    with path.open("a", newline="", encoding=CSV_ENCODING) as handle:
        writer = csv.DictWriter(handle, fieldnames=TIMESERIES_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "taken_at": taken_at.isoformat(timespec="seconds"),
            "count": count,
            "stated_count": stated if stated is not None else "",
            "complete": complete,
            "joined": " ".join(change.joined),
            "left": " ".join(change.left),
        })
