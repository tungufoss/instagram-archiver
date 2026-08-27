"""Where things live by default.

Media goes to the machine's real Pictures folder; the browser session goes to
a per-user data directory, not next to the code and not into cloud-synced
storage if we can help it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "instagram-archiver"

# Everything this tool saves lives under one root folder.
ARCHIVE_ROOT = "ig_archiver"

# Records about an account live beside its media, not mixed in with it:
# <out>/<account>/metadata/ holds the index, the post list, the
# comments and the follower history, while the pictures sit one level
# up where a file browser shows them without clutter.
METADATA_DIR = "metadata"

def default_browser_profile_dir() -> Path:
    """Per-user application data, where a live session belongs."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base) if base else Path.home() / ".local" / "share"

    return root / APP_NAME / "browser_profile"


def default_output_dir() -> Path:
    """Where media goes unless --out says otherwise.

    The working directory, so a run drops its files where you started it and
    you can move them wherever you like afterwards.
    """
    return Path.cwd() / ARCHIVE_ROOT


def metadata_dir(out_dir, username: str):
    """Where an account's records live."""
    return out_dir / account_dir_name(username) / METADATA_DIR


def account_dir_name(username: str) -> str:
    """Folder name for one account's media. Sanitised for the filesystem."""
    safe = "".join(c for c in username if c.isalnum() or c in "._-")
    return safe or "unknown-account"
