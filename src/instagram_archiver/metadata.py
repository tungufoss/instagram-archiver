"""Post metadata parsed from Open Graph tags.

Reels in particular render no <time> element and surround the media with
advertiser links, so the DOM is a poor source for "who posted this, and when".
The og:description tag carries both, in a stable shape:

    628K likes, 4,110 comments - someaccount on April 1, 2026: "caption..."
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# "- someaccount on April 1, 2026:"
OG_AUTHOR_DATE_RE = re.compile(
    r"-\s*(?P<username>[A-Za-z0-9._]+)\s+on\s+"
    r"(?P<date>[A-Z][a-z]+\s+\d{1,2},\s*\d{4})\s*:",
)

# Some posts omit the date but still name the author.
OG_AUTHOR_RE = re.compile(r"-\s*(?P<username>[A-Za-z0-9._]+)\s+on\s")


def parse_og_description(text: str | None) -> tuple[str | None, str | None]:
    """Return (username, YYYY-MM-DD) from an og:description, either may be None."""
    if not text:
        return None, None

    match = OG_AUTHOR_DATE_RE.search(text)
    if match:
        username = match.group("username")
        try:
            parsed = datetime.strptime(
                re.sub(r"\s+", " ", match.group("date")).strip(), "%B %d, %Y"
            )
        except ValueError:
            return username, None
        return username, parsed.strftime("%Y-%m-%d")

    fallback = OG_AUTHOR_RE.search(text)
    return (fallback.group("username") if fallback else None), None


def iso_to_epoch(stamp: str | None) -> float | None:
    """'2026-08-17T12:34:56.000Z' -> epoch seconds, or None."""
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def date_to_epoch(date: str | None) -> float | None:
    """'2026-08-17' -> epoch seconds at midnight UTC, or None."""
    if not date:
        return None
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return parsed.timestamp()
