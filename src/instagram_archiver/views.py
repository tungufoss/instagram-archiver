"""Play counts, read from the tiles on a profile's reels tab.

Instagram leaves `view_count` null in every post's page data, for viewers and
for the account itself. But the reels tab draws the number on each tile, and
that is visible when the account is looking at its own profile.

So views come from there: one pass over the reels tab, pairing each reel with
the count on its thumbnail. Nothing is inferred - if a tile shows no number,
that reel simply has no recorded count.
"""

from __future__ import annotations

import re

# "2,653", "1.2M", "866" - as drawn on the tile.
COUNT_RE = re.compile(r"^([\d.,]+)\s*([KM]?)$", re.I)

SCALES = {"": 1, "K": 1_000, "M": 1_000_000}

COLLECT_REEL_TILES_JS = """
() => {
  const main = document.querySelector('main');
  if (!main) return [];
  return [...main.querySelectorAll("a[href*='/reel/']")].map(a => ({
    href: a.getAttribute('href'),
    text: (a.innerText || '').trim(),
  }));
}
"""


def parse_count(text: str) -> int | None:
    """'2,653' -> 2653, '1.2M' -> 1200000, anything else -> None."""
    match = COUNT_RE.match((text or "").strip())
    if not match:
        return None
    digits, scale = match.group(1), match.group(2).upper()
    try:
        if scale:
            return int(float(digits.replace(",", "")) * SCALES[scale])
        return int(digits.replace(",", "").replace(".", ""))
    except (ValueError, KeyError):
        return None


def code_of(href: str) -> str | None:
    match = re.search(r"/reel/([A-Za-z0-9_-]+)", href or "")
    return match.group(1) if match else None


def from_tiles(tiles: list[dict]) -> dict[str, int]:
    """Post shortcode -> play count, for the tiles that showed one."""
    found: dict[str, int] = {}
    for tile in tiles or []:
        code = code_of(tile.get("href", ""))
        count = parse_count(tile.get("text", ""))
        if code and count is not None:
            found[code] = count
    return found
