"""Reading posts and profiles in the browser.

Everything here works only with what the authenticated page already shows.
There is no attempt to reach content the logged-in account cannot see.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from . import comments as comment_reader
from .config import (
    MAX_SLIDES,
    SCROLL_PAUSE,
    SCROLL_STAGNANT_LIMIT,
    SLIDE_PAUSE,
)
from .embedded import post_details, video_urls_by_position
from .extract import RESERVED, current_slide, read_comments, read_username
from .followerfeed import FollowerFeed
from .metadata import date_to_epoch, iso_to_epoch, parse_og_description
from .urls import (
    image_key,
    normalise_post_url,
    page_url_for,
    post_id_from,
)

# Instagram words this as "profile" or "account" depending on the surface.
PRIVATE_RE = re.compile(r"this (account|profile) is private", re.I)

# "603 followers" - the count itself is the control that opens the list,
# an <a href="#"> with no destination, so it has to be found by its text.
# The bare word is enough: the only other follow-related link on a profile
# reads "Followed by ... + 42 more", and "following" is a different word.
FOLLOWERS_COUNT_RE = re.compile("followers", re.I)

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
    caption: str = ""                   # the post's text, recorded in the index
    comments: list = field(default_factory=list)
    comment_count: int = 0              # how many the post has in total
    like_count: int = 0
    view_count: int | None = None
    timestamp_iso: str = ""             # the post's exact time, when known


class FollowersUnavailable(RuntimeError):
    """The profile does not offer its follower list to this account."""


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
                       max_slides=MAX_SLIDES, username_hint=None,
                       want_comments=False):
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
    details = post_details(page, post_id_from(post_url))
    known_videos = video_urls_by_position(details.items if details else None)

    meta = PostMeta(
        date=(iso[:10] if iso else None) or og_date or "unknown-date",
        username=(
            username_hint or og_username or read_username(page) or "unknown-account"
        ),
        # Prefer the exact <time> stamp; fall back to midnight on the og date.
        timestamp=iso_to_epoch(iso) or date_to_epoch(og_date),
        caption=details.caption if details else "",
        comments=details.comments if details else [],
        comment_count=details.comment_count if details else 0,
        like_count=details.like_count if details else 0,
        view_count=details.view_count if details else None,
        timestamp_iso=iso or og_date or "",
    )

    if want_comments and not meta.comments:
        # Not in the page JSON; read what the DOM has loaded.
        meta.comments = comment_reader.from_blocks(
            read_comments(page), caption=meta.caption, post_timestamp=iso or ""
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

def enumerate_profile_posts(page, profile_url, max_posts=None, include_reels=True,
                            record_skipped=None):
    """Scroll a profile and collect the post URLs this session can see.

    A profile links some of its own posts as `/reel/<code>/` - typically the
    ones holding only a video. They are the account's own content, so they are
    included by default; `--skip-reels` leaves them out, and `record_skipped`
    collects what was left behind.
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
        print(f"  skipped {len(skipped_reels)} post(s) linked as reels; drop "
              f"--skip-reels to include them")
    if not urls:
        print("  ! No posts were visible to this session. Open the profile in the")
        print("    Chromium window yourself to see what Instagram is showing you.")
    if skipped_reels and record_skipped is not None:
        record_skipped.extend(skipped_reels)

    return urls[:max_posts] if max_posts else urls


def scan_post(page, post_url, username_hint=None):
    """Describe a post without downloading anything.

    Everything needed is in the page: the media list, the counts and the
    caption. No carousel walking, so this is several times quicker than
    archiving and touches Instagram far less.
    """
    page.goto(page_url_for(post_url), wait_until="domcontentloaded")
    try:
        page.wait_for_selector("article img, article video, main img, main video",
                               timeout=20_000)
    except PlaywrightTimeout:
        pass

    code = post_id_from(post_url)
    details = post_details(page, code)
    og_username, og_date = parse_og_description(read_og_description(page))
    iso = read_post_timestamp(page)

    items = details.items if details else []
    return {
        "post_url": post_url,
        "post_id": code,
        "username": (username_hint or og_username
                     or read_username(page) or "unknown-account"),
        "post_date": (iso[:10] if iso else None) or og_date or "unknown-date",
        "post_time": iso or "",
        "kind": "reel" if "/reel/" in post_url else "post",
        "likes": details.like_count if details else 0,
        # Blank rather than zero when Instagram will not say.
        "views": (details.view_count if details else None),
        "comments": details.comment_count if details else 0,
        "images": sum(1 for i in items if i.get("kind") == "image"),
        "videos": sum(1 for i in items if i.get("kind") == "video"),
        "media_count": len(items),
        "caption": details.caption if details else "",
    }


# The follower dialog is a virtualised list: names load as it scrolls, and the
# ones scrolled past may be discarded, so every pass has to be collected.
COLLECT_DIALOG_HANDLES_JS = """
(reserved) => {
  const skip = new Set(reserved.split(','));
  const dialog = document.querySelector('div[role="dialog"]');
  if (!dialog) return null;
  const names = [];
  for (const a of dialog.querySelectorAll('a[href^="/"]')) {
    const parts = a.getAttribute('href').split('/').filter(Boolean);
    if (parts.length === 1 && !skip.has(parts[0].toLowerCase())) {
      names.push(parts[0]);
    }
  }
  return names;
}
"""

# Scroll by less than a screenful, never straight to the bottom. The list is
# virtualised: rows that are never rendered are never read, so jumping to the
# end skips most of the names. Overlapping steps keep every row passing
# through the window, and the caller checks the overlap actually held.
# A follower row is about 60px, so this advances a few rows at a time and
# always leaves part of the previous window on screen.
FOLLOWER_SCROLL_STEP = 240

DIALOG_HEIGHT_JS = """
() => {
  const dialog = document.querySelector('div[role="dialog"]');
  if (!dialog) return null;
  const boxes = [...dialog.querySelectorAll('*')].filter(
    el => el.scrollHeight > el.clientHeight + 40
  );
  if (!boxes.length) return null;
  return boxes.reduce((a, b) => (a.scrollHeight >= b.scrollHeight ? a : b))
              .scrollHeight;
}
"""

SCROLL_TO_JS = """
(top) => {
  const dialog = document.querySelector('div[role="dialog"]');
  if (!dialog) return;
  const boxes = [...dialog.querySelectorAll('*')].filter(
    el => el.scrollHeight > el.clientHeight + 40
  );
  if (!boxes.length) return;
  boxes.reduce((a, b) => (a.scrollHeight >= b.scrollHeight ? a : b)).scrollTop = top;
}
"""

SCROLL_BY_JS = """
(pixels) => {
  const dialog = document.querySelector('div[role="dialog"]');
  if (!dialog) return null;
  const boxes = [...dialog.querySelectorAll('*')].filter(
    el => el.scrollHeight > el.clientHeight + 40
  );
  if (!boxes.length) return null;
  const box = boxes.reduce((a, b) => (a.scrollHeight >= b.scrollHeight ? a : b));

  const before = box.scrollTop;
  box.scrollTop = Math.min(before + pixels, box.scrollHeight - box.clientHeight);
  return {
    moved: box.scrollTop - before,
    atEnd: box.scrollTop + box.clientHeight >= box.scrollHeight - 4,
  };
}
"""


def read_followers(page, profile_url, max_rounds=200):
    """The usernames the follower dialog will show us.

    Reads only what the profile offers: if you cannot open the list yourself,
    neither can this.
    """
    page.goto(profile_url, wait_until="domcontentloaded")
    page.wait_for_selector("main", timeout=20_000)

    if PRIVATE_RE.search(page.inner_text("body")[:4_000]):
        raise PrivateProfile(
            "This profile is private and the account you are logged in as does "
            "not follow it, so its followers are not visible."
        )

    # The count itself opens the list. It is an <a href="#"> - a link with no
    # destination - so it has to be found by its text, not its href. The
    # /followers/mutualOnly link nearby is a different thing: the handful you
    # both follow, which must never be mistaken for the whole list.
    stated = None
    try:
        header = page.inner_text("main")[:400]
        match = re.search(r"([\d.,]+)\s*([KM]?)\s+followers", header, re.I)
        if match:
            digits = match.group(1).replace(",", "").replace(".", "")
            scale = {"K": 1_000, "M": 1_000_000}.get(match.group(2).upper(), 1)
            stated = int(digits) * scale
    except Exception:
        stated = None

    opener = page.locator("main a, main [role='button']").filter(
        has_text=FOLLOWERS_COUNT_RE
    ).first
    try:
        # The header fills in after <main> exists, so give the count a moment
        # to appear rather than deciding it is absent.
        opener.wait_for(state="attached", timeout=15_000)
    except PlaywrightTimeout:
        pass
    if not opener.count():
        raise FollowersUnavailable(
            "This profile does not offer its follower list to your account."
        )
    opener.click()

    try:
        page.wait_for_selector('div[role="dialog"]', timeout=20_000)
    except PlaywrightTimeout as exc:
        raise FollowersUnavailable("The followers list did not open.") from exc
    time.sleep(2.0)

    # The dialog's rows are virtualised, so reading them while scrolling always
    # misses names. The responses that fill the dialog carry every name once,
    # so listen to those and scroll only to make Instagram send the next page.
    feed = FollowerFeed(page)
    seen: dict[str, None] = {}
    for name in page.evaluate(COLLECT_DIALOG_HANDLES_JS, RESERVED) or []:
        seen.setdefault(name, None)

    stagnant = 0
    for _ in range(max_rounds):
        before = len(feed.names) + len(seen)
        if page.evaluate(SCROLL_BY_JS, 100_000) is None:
            break
        time.sleep(1.2)

        for name in page.evaluate(COLLECT_DIALOG_HANDLES_JS, RESERVED) or []:
            seen.setdefault(name, None)

        total = len({*feed.names, *seen})
        print(f"  ...{total} follower(s) so far", flush=True)
        if len(feed.names) + len(seen) == before:
            stagnant += 1
            if stagnant >= 6:
                break
        else:
            stagnant = 0

    # The feed is authoritative; anything the DOM caught that it missed is
    # still worth keeping.
    collected = {*feed.names, *seen}
    collected.discard("")
    seen = dict.fromkeys(sorted(collected))
    breaks = 0
    if feed.responses:
        print(f"  read {feed.responses} response(s) from Instagram")

    print(f"  found {len(seen)} follower(s).")
    if breaks:
        print(f"  (slowed down {breaks} time(s) to avoid skipping names)")
    if stated and len(seen) < stated:
        # Better to say the list is short than to file it as though complete.
        print(f"  ! the profile says {stated}; this run saw {len(seen)}.")
        print("    This snapshot is incomplete.")
    return list(seen), stated
