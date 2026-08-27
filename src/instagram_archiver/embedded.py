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
from dataclasses import dataclass, field
from datetime import datetime, timezone

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


@dataclass
class Comment:
    """One comment, as recorded alongside the archive."""

    username: str
    timestamp: str          # ISO 8601, or "" when the page did not say
    text: str


@dataclass
class PostData:
    """What the page says about one post."""

    items: list[dict] = field(default_factory=list)
    caption: str = ""
    comments: list[Comment] = field(default_factory=list)
    comment_count: int = 0      # how many the post has, not how many we read
    like_count: int = 0
    # Instagram carries the field but leaves it null in the served page,
    # even on a reel with hundreds of thousands of likes, so this is
    # read but not recorded anywhere. Kept in case that changes.
    view_count: int | None = None   # None means Instagram did not tell us


def _caption_of(media: dict) -> str:
    caption = media.get("caption")
    if isinstance(caption, dict):
        text = caption.get("text")
        if isinstance(text, str):
            return text.strip()
    if isinstance(caption, str):
        return caption.strip()
    return ""


def _epoch_to_iso(value) -> str:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def _comment_from(node: dict) -> Comment | None:
    """Read one comment, tolerating the shapes Instagram has used."""
    if not isinstance(node, dict):
        return None

    text = node.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    owner = node.get("user") or node.get("owner") or {}
    username = owner.get("username") if isinstance(owner, dict) else None
    if not isinstance(username, str):
        username = node.get("username") if isinstance(node.get("username"), str) else ""

    return Comment(
        username=username or "",
        timestamp=_epoch_to_iso(node.get("created_at") or node.get("created_at_utc")),
        text=text.strip(),
    )


def _int_of(media: dict, key: str) -> int:
    try:
        return max(int(media.get(key) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _count_of(media: dict) -> int:
    return _int_of(media, "comment_count")


# Instagram has called this several things over the years, and a carousel
# reports plays per slide rather than for the post.
VIEW_KEYS = ("play_count", "view_count", "video_play_count", "ig_play_count")


def _views_of(media: dict, items: list[dict]) -> int | None:
    """Play count, or None when the page does not carry one.

    Instagram leaves these null for anyone who is not the account itself, and
    a null is not a zero: recording 0 would claim nobody watched.
    """
    for key in VIEW_KEYS:
        if media.get(key) is not None:
            return _int_of(media, key)

    total = None
    for slide in media.get("carousel_media") or []:
        if not isinstance(slide, dict):
            continue
        for key in VIEW_KEYS:
            if slide.get(key) is not None:
                total = (total or 0) + _int_of(slide, key)
                break
    return total


def _comments_of(media: dict) -> list[Comment]:
    """Comments carried by the post object, in the order the page lists them.

    Instagram has used several shapes for this, and a server-rendered page
    often carries only `preview_comments` - the handful shown before you press
    "view all". Whatever is there is what gets recorded.
    """
    raw = media.get("comments")
    if raw is None:
        raw = media.get("preview_comments")
    if raw is None:
        edges = (media.get("edge_media_to_parent_comment")
                 or media.get("edge_media_to_comment") or {})
        raw = edges.get("edges") if isinstance(edges, dict) else None
        if isinstance(raw, list):
            raw = [e.get("node") for e in raw if isinstance(e, dict)]

    if not isinstance(raw, list):
        return []

    found = []
    for node in raw:
        comment = _comment_from(node)
        if comment is not None:
            found.append(comment)
    return found


def parse_post(blocks: list[str], code: str) -> PostData | None:
    """Media list and caption for one post, from the page's JSON blocks."""
    found: list[dict] = []
    for block in blocks:
        if not block or code not in block:
            continue
        try:
            _walk(json.loads(block), code, found)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    best: PostData | None = None
    for media in found:
        items = media.get("carousel_media") or [media]
        if not isinstance(items, list) or not items:
            continue
        if not any(
            isinstance(i, dict) and ("video_versions" in i or "image_versions2" in i)
            for i in items
        ):
            # No media detail, but it may still carry the caption.
            caption = _caption_of(media)
            if caption and best is None:
                best = PostData(items=[], caption=caption)
            continue

        parsed = []
        for item in items:
            if not isinstance(item, dict):
                parsed.append({"kind": "image"})
                continue
            video = _best_video(item)
            parsed.append({"kind": "video", **video} if video else {"kind": "image"})
        return PostData(items=parsed, caption=_caption_of(media),
                        comments=_comments_of(media),
                        comment_count=_count_of(media),
                        like_count=_int_of(media, "like_count"),
                        view_count=_views_of(media, parsed))

    return best


def parse_blocks(blocks: list[str], code: str) -> list[dict] | None:
    """Turn the page's JSON blocks into an ordered media list for one post.

    Returns one entry per carousel slide - `{"kind": "video", "url": ...}` or
    `{"kind": "image"}` - or None when the post is not described in them.
    """
    post = parse_post(blocks, code)
    return post.items if post and post.items else None


def post_details(page, code: str) -> PostData | None:
    """Read the media list and caption for `code` out of the current page."""
    try:
        blocks = page.evaluate(COLLECT_JSON_BLOCKS_JS)
    except Exception:
        return None
    if not blocks:
        return None
    return parse_post(blocks, code)


def post_media(page, code: str) -> list[dict] | None:
    """Just the media list, for callers that do not need the caption."""
    details = post_details(page, code)
    return details.items if details and details.items else None


def video_urls_by_position(media: list[dict] | None) -> dict[int, str]:
    """1-based slide position -> video URL, for the slides that hold videos."""
    if not media:
        return {}
    return {
        position: item["url"]
        for position, item in enumerate(media, start=1)
        if item.get("kind") == "video" and item.get("url")
    }
