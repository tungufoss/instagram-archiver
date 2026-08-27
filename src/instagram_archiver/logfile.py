"""Write everything printed to a log file as well as the terminal.

Piping to `tee` works, but it is easy to forget and it silently produces no
log at all when you do. A run that took twenty minutes deserves a record
without the caller having to remember anything.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

DEFAULT_NAME = "archive.log"


class _Tee:
    """Forwards writes to the real stream and to an open file."""

    def __init__(self, stream, handle):
        self._stream = stream
        self._handle = handle

    def write(self, text: str) -> int:
        self._handle.write(text)
        self._handle.flush()
        return self._stream.write(text)

    def flush(self) -> None:
        self._handle.flush()
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def start(path: Path) -> Path:
    """Begin copying stdout and stderr into `path`. Appends across runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a", encoding="utf-8", errors="replace")
    handle.write(
        f"\n{'=' * 70}\n"
        f"run started {datetime.now().isoformat(timespec='seconds')}\n"
        f"command: {' '.join(sys.argv)}\n"
        f"{'=' * 70}\n"
    )
    handle.flush()

    sys.stdout = _Tee(sys.stdout, handle)
    sys.stderr = _Tee(sys.stderr, handle)
    return path
