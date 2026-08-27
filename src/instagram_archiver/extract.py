"""JavaScript evaluated inside the page.

Both snippets run in the authenticated tab, so they see exactly what a person
looking at the same page would see - nothing more.
"""

from __future__ import annotations

from .config import MIN_IMAGE_PIXELS

# Collect candidate photographs from the post currently rendered.
#
# Instagram does not always wrap a standalone post in <article>, so we fall
# back to <main>. That means the "more posts" grid is in scope, and the
# discriminator that actually works is this: a suggested post's thumbnail is
# always inside an <a href="/p/..."> link, while the post's own media never
# is. Size alone is not enough - suggestion thumbnails can exceed 300px.
EXTRACT_IMAGES_JS = """
(minPixels) => {
  const art = document.querySelector('article') || document.querySelector('main');
  if (!art) return [];
  const out = [];
  for (const img of art.querySelectorAll('img')) {
    if (img.closest('header')) continue;                     // profile pic
    if (img.closest("a[href*='/p/'], a[href*='/reel/']")) continue;  // suggested
    const alt = img.getAttribute('alt') || '';
    if (/profile picture/i.test(alt)) continue;
    const holder = img.closest('li') || img.parentElement;
    if (holder && holder.querySelector('video')) continue;   // video poster
    let best = img.currentSrc || img.src || '';
    let bestW = 0;
    const srcset = img.getAttribute('srcset') || '';
    for (const part of srcset.split(',')) {
      const m = part.trim().match(/^(\\S+)\\s+(\\d+)w$/);
      if (m && parseInt(m[2], 10) > bestW) { bestW = parseInt(m[2], 10); best = m[1]; }
    }
    if (!/^https?:/.test(best)) continue;
    if (img.clientWidth < minPixels || img.clientHeight < minPixels) continue;
    out.push({ url: best, width: bestW, alt: alt });
  }
  return out;
}
"""

# A <video> exposes a blob: src, which cannot be downloaded. Starting playback
# muted makes the page fetch the real CDN file, which the request sniffer sees.
NUDGE_VIDEOS_JS = """
() => {
  const art = document.querySelector('article') || document.querySelector('main');
  if (!art) return 0;
  let n = 0;
  for (const v of art.querySelectorAll('video')) {
    try {
      v.muted = true;
      const p = v.play();
      if (p && p.catch) p.catch(() => {});
      n++;
    } catch (e) { /* autoplay refused; the media request still fires */ }
  }
  return n;
}
"""


# The author's handle. Taken from the first single-segment profile link in
# the post header, skipping Instagram's own navigation destinations. Used only
# when the caller has no better source; profile mode passes the name straight in.
RESERVED = "explore,reels,direct,accounts,stories,about,legal,privacy,terms,p,reel"

READ_USERNAME_JS = """
(reserved) => {
  const skip = new Set(reserved.split(','));
  const root = document.querySelector('article') || document.querySelector('main');
  if (!root) return null;
  const header = root.querySelector('header') || root;
  for (const a of header.querySelectorAll('a[href^="/"]')) {
    if (a.closest("a[href*='/p/'], a[href*='/reel/']")) continue;
    const parts = a.getAttribute('href').split('/').filter(Boolean);
    if (parts.length === 1 && !skip.has(parts[0].toLowerCase())) return parts[0];
  }
  return null;
}
"""


def read_username(page) -> str | None:
    """The account that posted whatever is currently rendered."""
    try:
        return page.evaluate(READ_USERNAME_JS, RESERVED)
    except Exception:
        return None


def extract_images(page):
    """Return the photo candidates visible in the current post."""
    return page.evaluate(EXTRACT_IMAGES_JS, MIN_IMAGE_PIXELS)


def nudge_videos(page) -> int:
    """Start any videos muted; returns how many were nudged."""
    try:
        return page.evaluate(NUDGE_VIDEOS_JS) or 0
    except Exception:
        return 0
