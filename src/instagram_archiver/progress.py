"""A dependency-free progress line, friendly to both terminals and log files."""

from __future__ import annotations

import time

BAR_WIDTH = 24


def _clock(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def bar(done: int, total: int, width: int = BAR_WIDTH) -> str:
    if total <= 0:
        return "-" * width
    filled = int(width * done / total)
    return "#" * filled + "." * (width - filled)


def line(done: int, total: int, files: int, started: float,
         now: float | None = None) -> str:
    """One self-contained status line, printed after each post."""
    now = time.time() if now is None else now
    elapsed = now - started
    percent = (100 * done / total) if total else 0.0

    if done and total and done < total:
        eta = f" | ~{_clock(elapsed / done * (total - done))} left"
    else:
        eta = ""

    return (
        f"  [{bar(done, total)}] {percent:5.1f}%  "
        f"{done}/{total} posts | {files} files | {_clock(elapsed)} elapsed{eta}"
    )
