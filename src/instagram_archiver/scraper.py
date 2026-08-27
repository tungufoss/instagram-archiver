"""Reading posts and profiles in the browser.

Everything here works only with what the authenticated page already shows.
There is no attempt to reach content the logged-in account cannot see.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .config import (
    MAX_SLIDES,
    SCROLL_PAUSE,
    SCROLL_STAGNANT_LIMIT,
    SLIDE_PAUSE,
)
from .embedded import post_media, video_urls_by_position
from .extract import current_slide, read_username
from .metadata import date_to_epoch, iso_to_epoch, parse_og_description
from .urls import image_key, normalise_post_url, page_url_for, post_id_from

# Instagram words this as "profile" or "account" depending on the surface.
PRIVATE_RE = re.compile(r"this (account|profile) is private", re.I)

# A standalone post is sometimes an <article>, sometimes only <main>, so
# every selector below has to tolerate both.
POST_MEDIA_SELECTOR = "article img, article video, main img, main video"
POST_TIME_SELECTOR = "article time[datetime], main time[datetime]"

NEXT_SELECTORS = (
    'article button[aria-label="Next"]',
    'article div[role="button"][aria-label="Next"]',
    'main button[aria-label="Next"]',
    'main div[role="button"][aria-label="Next"]',
    'button[aria-label="Next"]',
)


@dataclass
class PostMeta:
    """What we know about a post besides its media."""

    date: str = "unknown-date"          # YYYY-MM-DD, used in folder names
    username: str = "unknown-account"
    timestamp: float | None = None      # epoch seconds, applied to saved files


class PrivateProfile(RuntimeError):
    """The logged-in account cannot see this profile's posts."""


def nap(bounds: tuple[float, float]) -> None:
    time.sleep(random.uniform(*bounds))


# ---------------------------------------------------------- post reading ---

def read_og_description(page) -> str | None:
    try:
        meta = page.locator('meta[property="og:description"]').first
        if meta.count():
            return meta.get_attribute("content", timeout=2_000)
    except Exception:
        pass
    return None


def read_post_timestamp(page) -> str | None:
    """The post's own <time datetime=...>, full ISO string, if present."""
    try:
        stamp = page.locator(POST_TIME_SELECTOR).first.get_attribute(
            "datetime", timeout=5_000
        )
        return stamp or None
    except Exception:
        return None


def next_button(page):
    """The carousel's Next control, or None when the last slide is showing."""
    for selector in NEXT_SELECTORS:
        locator = page.locator(selector).first
        try:
            if locator.count() and locator.is_visible():
                return locator
        except Exception:
            continue
    return None


def collect_post_media(page, post_url, want_videos=True,
                       max_slides=MAX_SLIDES, username_hint=None):
    """Open a post, walk every carousel slide.

    Returns (PostMeta, items).
    """
    # Always the /p/ form: a reel page omits the embedded media list.
    page.goto(page_url_for(post_url), wait_until="domcontentloaded")
    try:
        page.wait_for_selector(POST_MEDIA_SELECTOR, timeout=20_000)
    except PlaywrightTimeout:
        print(f"  ! nothing rendered for {post_url} (deleted, or not visible to you)")
        return PostMeta(), []

    # Reels render no <time> and surround the media with advertiser links, so
    # og:description is the most reliable source for both facts.
    og_username, og_date = parse_og_description(read_og_description(page))
    iso = read_post_timestamp(page)

    # The page carries the post's own media list; when it is there we know
    # exactly which video belongs to which slide instead of inferring it.
    known_videos = video_urls_by_position(post_media(page, post_id_from(post_url)))

    meta = PostMeta(
        date=(iso[:10] if iso else None) or og_date or "unknown-date",
        username=(
            username_hint or og_username or read_username(page) or "unknown-account"
        ),
        # Prefer the exact <time> stamp; fall back to midnight on the og date.
        timestamp=iso_to_epoch(iso) or date_to_epoch(og_date),
    )
    items: list[dict] = []
    seen_images: set[str] = set()

    def harvest() -> None:
        """Record whatever is on the slide currently being shown."""
        slide = current_slide(page)
        if slide is None:
            return

        if slide["kind"] == "image":
            key = image_key(slide["url"])
            if key in seen_images:          # the slide did not actually change
                return
            seen_images.add(key)
            items.append(
                {"kind": "image", "url": slide["url"], "width": slide["width"]}
            )
            return

        # A video occupies this slide.
        if not want_videos:
            # Note the gap so the numbering keeps the post's real shape.
            items.append({"kind": "video_skipped"})
            return

        position = len(items) + 1
        known = known_videos.get(position)
        if known:
            # Named by the page itself: no playback, no sniffing, no guessing.
            items.append({"kind": "video", "urls": [known], "width": 0})
            return

        # Nothing authoritative for this slide. Watching traffic is guesswork
        # (the browser prefetches other posts' videos), so rather than risk
        # filing someone else's video, record the gap and move on.
        print(f"    ! slide {position}: the page did not name its video, skipping")
        items.append({"kind": "video_skipped"})

    harvest()
    for _ in range(max_slides):
        button = next_button(page)
        if button is None:
            break
        try:
            button.click(timeout=5_000)
        except Exception:
            break
        nap(SLIDE_PAUSE)
        harvest()

    return meta, items


# ------------------------------------------------------- profile reading ---

def enumerate_profile_posts(page, profile_url, max_posts=None, include_reels=False,
                            record_skipped=None):
    """Scroll a profile and collect the post URLs this session can see.

    Reels are skipped by default: they carry no photographs, and their video
    cannot currently be attributed reliably (see the README). Pass
    `record_skipped` a list to find out which ones were left out.
    """
    page.goto(profile_url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("main", timeout=20_000)
    except PlaywrightTimeout:
        pass

    if PRIVATE_RE.search(page.inner_text("body")[:4_000]):
        raise PrivateProfile(
            "This profile is private and the account you are logged in as does not\n"
            "follow it, so Instagram serves none of its posts.\n"
            "\n"
            "Fix it one of these ways, then re-run:\n"
            "  * Follow the account in Instagram and wait to be accepted.\n"
            "  * Log in as an account that already follows it: delete the browser\n"
            "    profile directory and run `login` again.\n"
            "\n"
            "This tool will not work around that restriction."
        )

    urls: list[str] = []
    seen: set[str] = set()
    skipped_reels: list[str] = []
    stagnant = 0

    while stagnant < SCROLL_STAGNANT_LIMIT:
        hrefs = page.eval_on_selector_all(
            "main a[href]", "els => els.map(e => e.getAttribute('href'))"
        )
        before = len(seen)
        for href in hrefs:
            url = normalise_post_url(href or "")
            if not url or url in seen:
                continue
            seen.add(url)
            if "/reel/" in url and not include_reels:
                skipped_reels.append(url)
                continue
            urls.append(url)

        if max_posts and len(urls) >= max_posts:
            break

        stagnant = stagnant + 1 if len(seen) == before else 0
        page.mouse.wheel(0, 2_200)
        nap(SCROLL_PAUSE)
        print(f"  ...{len(urls)} posts found so far", end="\r", flush=True)

    print(f"  found {len(urls)} posts on the profile." + " " * 20)
    if skipped_reels:
        print(f"  skipped {len(skipped_reels)} reels; use --include-reels to "
              f"archive them too")
        print("    (a reel carries no photographs, so a photos-only archive")
        print("     loses nothing by skipping it)")
    if not urls:
        print("  ! No posts were visible to this session. Open the profile in the")
        print("    Chromium window yourself to see what Instagram is showing you.")
    if skipped_reels and record_skipped is not None:
        record_skipped.extend(skipped_reels)

    return urls[:max_posts] if max_posts else urls
