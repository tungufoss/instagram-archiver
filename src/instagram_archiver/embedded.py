"""The post's own media list, read from the page instead of guessed.

Instagram server-renders the post into the HTML as JSON, including a
`carousel_media` array with a `video_versions` list per slide. That is the
authoritative answer to "which video belongs to slide 4", which watching
network traffic never was: the browser also prefetches videos belonging to
other posts, and picking among them by size or arrival order guesses wrong
often enough to put a stranger's video in a family album.

Nothing here requests anything. It reads what the page was already served.
"""

from __future__ import annotations

import json

COLLECT_JSON_BLOCKS_JS = """
() => [...document.querySelectorAll('script[type="application/json"]')]
        .map(s => s.textContent)
"""


def _walk(node, code: str, found: list) -> None:
    """Collect every object describing the post with this shortcode."""
    if isinstance(node, dict):
        if node.get("code") == code:
            found.append(node)
        for value in node.values():
            _walk(value, code, found)
    elif isinstance(node, list):
        for value in node:
            _walk(value, code, found)


def _best_video(item: dict) -> dict | None:
    versions = item.get("video_versions") or []
    if not versions:
        return None
    best = max(
        versions,
        key=lambda v: (int(v.get("width") or 0) * int(v.get("height") or 0)),
    )
    url = best.get("url")
    if not isinstance(url, str) or not url.startswith("http"):
        return None
    return {
        "url": url,
        "width": int(best.get("width") or 0),
        "height": int(best.get("height") or 0),
    }


def parse_blocks(blocks: list[str], code: str) -> list[dict] | None:
    """Turn the page's JSON blocks into an ordered media list for one post.

    Returns one entry per carousel slide - `{"kind": "video", "url": ...}` or
    `{"kind": "image"}` - or None when the post is not described in them.
    """
    found: list[dict] = []
    for block in blocks:
        if not block or code not in block:
            continue
        try:
            _walk(json.loads(block), code, found)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    for media in found:
        items = media.get("carousel_media") or [media]
        if not isinstance(items, list) or not items:
            continue
        # A description without any media detail tells us nothing useful.
        if not any(
            isinstance(i, dict) and ("video_versions" in i or "image_versions2" in i)
            for i in items
        ):
            continue

        out = []
        for item in items:
            if not isinstance(item, dict):
                out.append({"kind": "image"})
                continue
            video = _best_video(item)
            out.append({"kind": "video", **video} if video else {"kind": "image"})
        return out

    return None


def post_media(page, code: str) -> list[dict] | None:
    """Read the media list for `code` out of the current page."""
    try:
        blocks = page.evaluate(COLLECT_JSON_BLOCKS_JS)
    except Exception:
        return None
    if not blocks:
        return None
    return parse_blocks(blocks, code)


def video_urls_by_position(media: list[dict] | None) -> dict[int, str]:
    """1-based slide position -> video URL, for the slides that hold videos."""
    if not media:
        return {}
    return {
        position: item["url"]
        for position, item in enumerate(media, start=1)
        if item.get("kind") == "video" and item.get("url")
    }
