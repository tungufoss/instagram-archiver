"""Pure URL helpers. No Playwright, no I/O - trivially testable."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

from .config import CDN_HOSTS

POST_RE = re.compile(r"/(p|reel)/([A-Za-z0-9_-]+)")
IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp|heic)$", re.I)
KEEPABLE_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Range parameters a video player adds when it streams a file piecemeal.
RANGE_PARAMS = ("bytestart", "byteend")


def post_id_from(url: str) -> str:
    """'https://instagram.com/p/ABC123/' -> 'ABC123'."""
    match = POST_RE.search(urlparse(url).path)
    return match.group(2) if match else "unknown"


def normalise_post_url(href: str) -> str | None:
    """Reduce any post/reel link to its canonical form, or None if it isn't one."""
    match = POST_RE.search(urlparse(href or "").path)
    if not match:
        return None
    return f"https://www.instagram.com/{match.group(1)}/{match.group(2)}/"


RESERVED_PATHS = {
    "p", "reel", "reels", "explore", "stories", "direct", "accounts",
    "about", "developer", "legal", "privacy", "terms",
}


def username_from_profile_url(url: str) -> str | None:
    """'https://instagram.com/someone/?hl=en' -> 'someone'."""
    parts = [part for part in urlparse(url or "").path.split("/") if part]
    if not parts:
        return None
    candidate = parts[0]
    if candidate.lower() in RESERVED_PATHS:
        return None
    return candidate


def image_key(url: str) -> str:
    """A photo is served at many sizes; its CDN path basename is stable."""
    return IMAGE_EXT_RE.sub("", Path(urlsplit(url).path).name)


def image_extension(url: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if suffix in KEEPABLE_IMAGE_EXTS else ".jpg"


def is_cdn_host(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return any(part in host for part in CDN_HOSTS)


def is_video_request(url: str) -> bool:
    """True for an .mp4 served by an Instagram/Facebook CDN."""
    return urlsplit(url).path.lower().endswith(".mp4") and is_cdn_host(url)


def clean_video_url(url: str) -> str:
    """Drop the byte-range parameters so the CDN returns the whole file."""
    parts = urlsplit(url)
    query = [
        item
        for item in parse_qsl(parts.query, keep_blank_values=True)
        if item[0] not in RANGE_PARAMS
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def video_key(url: str) -> str:
    return Path(urlsplit(url).path).name


def page_url_for(post_url: str) -> str:
    """The URL to actually open for a post.

    A reel served at /reel/<code>/ does not carry the post's media in its
    embedded JSON, while the very same code at /p/<code>/ does. Always read
    the /p/ form; the original URL is still what gets recorded.
    """
    match = POST_RE.search(urlparse(post_url or "").path)
    if not match:
        return post_url
    return f"https://www.instagram.com/p/{match.group(2)}/"
