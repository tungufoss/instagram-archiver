"""JavaScript evaluated inside the page.

Both snippets run in the authenticated tab, so they see exactly what a person
looking at the same page would see - nothing more.
"""

from __future__ import annotations

from .config import MIN_IMAGE_PIXELS

# A <video> exposes a blob: src, which cannot be downloaded. Starting playback
# muted makes the page fetch the real CDN file, which the request sniffer sees.
#
# Only the post's OWN video may be nudged. The suggested-reels strip below a
# post contains <video> elements too, and playing those makes the page fetch
# their files, which the sniffer would then file as part of this post. They are
# excluded the same way suggested images are: they sit inside an <a href="/p/">.
NUDGE_VIDEOS_JS = """
() => {
  const root = document.querySelector('article') || document.querySelector('main');
  if (!root) return 0;
  let n = 0;
  for (const v of root.querySelectorAll('video')) {
    if (v.closest("a[href*='/p/'], a[href*='/reel/']")) continue;   // suggested
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

# Instagram mounts three carousel slides at once: the previous one off to the
# left, the current one, and the next one off to the right. Reading them all
# attributes the *next* slide's media to the current position - which produced
# 16 files for a 12-slide post, with placeholders on slides that held photos.
#
# The current slide is the one lying wholly inside the viewport; its neighbours
# are translated so that part of them hangs off an edge. Visible fraction picks
# it out without depending on Instagram's class names or layout maths.
CURRENT_SLIDE_JS = r"""
(minPixels) => {
  const root = document.querySelector('article') || document.querySelector('main');
  if (!root) return null;

  const vw = window.innerWidth;
  const suggested = el => el.closest("a[href*='/p/'], a[href*='/reel/']");

  const candidates = [];
  for (const el of root.querySelectorAll('img, video')) {
    if (suggested(el)) continue;
    if (el.tagName === 'IMG') {
      if (el.closest('header')) continue;
      if (/profile picture/i.test(el.getAttribute('alt') || '')) continue;
    }
    const r = el.getBoundingClientRect();
    if (r.width < minPixels || r.height < minPixels) continue;

    const visible = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0));
    if (visible <= 0) continue;
    candidates.push({ el, fraction: visible / r.width });
  }
  if (!candidates.length) return null;

  // Strictly the largest visible fraction; DOM order breaks ties.
  let best = candidates[0];
  for (const c of candidates) {
    if (c.fraction > best.fraction) best = c;
  }
  const el = best.el;

  if (el.tagName === 'VIDEO') return { kind: 'video' };

  let url = el.currentSrc || el.src || '';
  let width = 0;
  for (const part of (el.getAttribute('srcset') || '').split(',')) {
    const m = part.trim().match(/^(\S+)\s+(\d+)w$/);
    if (m && parseInt(m[2], 10) > width) { width = parseInt(m[2], 10); url = m[1]; }
  }
  if (!/^https?:/.test(url)) return null;
  return { kind: 'image', url: url, width: width };
}
"""


def current_slide(page):
    """What is on the slide being shown right now, or None."""
    try:
        return page.evaluate(CURRENT_SLIDE_JS, MIN_IMAGE_PIXELS)
    except Exception:
        return None


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


def nudge_videos(page) -> int:
    """Start the post's own videos muted; returns how many were nudged."""
    try:
        return page.evaluate(NUDGE_VIDEOS_JS) or 0
    except Exception:
        return 0



# Comments are not server-rendered into the page JSON - `preview_comments` is
# an empty list even on a post with four thousand of them. They are in the DOM
# though, each with an exact timestamp, so that is where they are read from.
#
# Only what the page has loaded is taken. Instagram shows a dozen or so and
# paginates the rest behind "view more"; clicking through thousands of other
# people's remarks is not something this tool should do.
READ_COMMENTS_JS = """
() => {
  const root = document.querySelector('article') || document.querySelector('main');
  if (!root) return [];

  const handleOf = el => {
    const link = [...el.querySelectorAll('a[href^="/"]')].find(a => {
      const parts = a.getAttribute('href').split('/').filter(Boolean);
      return parts.length === 1;
    });
    return link ? link.getAttribute('href').split('/').filter(Boolean)[0] : null;
  };

  const out = [];
  for (const time of root.querySelectorAll('time[datetime]')) {
    let node = time.parentElement;
    let holder = null;
    for (let i = 0; i < 8 && node; i++) {
      if (handleOf(node)) { holder = node; break; }
      node = node.parentElement;
    }
    if (!holder) continue;
    out.push({
      username: handleOf(holder),
      datetime: time.getAttribute('datetime'),
      block: holder.innerText || '',
    });
  }
  return out;
}
"""


def read_comments(page):
    """Raw comment blocks from the page, for cleaning in Python."""
    try:
        return page.evaluate(READ_COMMENTS_JS) or []
    except Exception:
        return []
