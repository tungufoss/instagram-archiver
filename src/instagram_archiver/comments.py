"""Turning what the page shows into comment rows.

Instagram does not put comments in the page's embedded JSON - a post with four
thousand of them reports `preview_comments: []` - so they are read from the
rendered DOM instead. Each carries an exact timestamp, which is the part worth
having.

Only the comments the page has already loaded are taken. Instagram shows a
dozen or so and hides the rest behind "view more"; clicking through thousands
of other people's remarks is not something this tool should do.
"""

from __future__ import annotations

import re

from .embedded import Comment

# Interface furniture that sits inside a comment block and is not the comment.
NOISE = {
    "reply", "follow", "following", "see translation", "translate",
    "verified", "edited", "view replies", "hide replies", "like",
}
NOISE_PATTERNS = (
    re.compile(r"^view all \d[\d,.]* repl(y|ies)$", re.I),
    re.compile(r"^view \d[\d,.]* repl(y|ies)$", re.I),
    re.compile(r"^\d[\d,.]*\s+likes?$", re.I),
    re.compile(r"^\d+[smhdw]$", re.I),          # relative age: 7w, 10h
    re.compile(r"^\d+ (second|minute|hour|day|week|year)s? ago$", re.I),
)


def _is_noise(line: str, username: str) -> bool:
    lowered = line.strip().lower()
    if not lowered or lowered in NOISE:
        return True
    if lowered == username.lower():
        return True
    return any(p.match(line.strip()) for p in NOISE_PATTERNS)


def clean_block(username: str, block: str) -> str:
    """The comment text, with the surrounding interface stripped out."""
    lines = [line.strip() for line in (block or "").splitlines()]
    kept = [line for line in lines if not _is_noise(line, username or "")]
    return "\n".join(kept).strip()


def from_blocks(raw: list[dict], caption: str = "",
                post_timestamp: str = "") -> list[Comment]:
    """Build comment rows, leaving out the post's own caption.

    The caption sits in the same shape as a comment - author, time, text - so
    it is excluded by matching either its timestamp or its text.
    """
    found: list[Comment] = []
    seen: set[tuple[str, str, str]] = set()

    for item in raw or []:
        username = (item.get("username") or "").strip()
        stamp = (item.get("datetime") or "").strip()
        text = clean_block(username, item.get("block", ""))
        if not text:
            continue
        if post_timestamp and stamp == post_timestamp:
            continue                                  # this is the caption
        if caption and text == caption.strip():
            continue

        key = (username, stamp, text)
        if key in seen:
            continue
        seen.add(key)
        found.append(Comment(username=username, timestamp=stamp, text=text))

    return found
