"""Tunable constants.

Pacing is deliberately conservative: this tool browses like a person, and
nothing here should be raised to hammer Instagram.
"""

from __future__ import annotations

# Hosts that serve Instagram media. Used to ignore unrelated requests.
CDN_HOSTS = ("cdninstagram", "fbcdn")

# Anything smaller is an icon, a placeholder or an empty range response.
MIN_IMAGE_BYTES = 5_000
MIN_VIDEO_BYTES = 50_000

# A separate audio track is a small fraction of the video it belongs to.
# Anything larger than this share of the biggest candidate is just a
# lower-bitrate copy of the same picture, not worth downloading.
AUDIO_SIZE_RATIO = 0.25

# On-screen size below which an <img> is treated as chrome, not content.
MIN_IMAGE_PIXELS = 200

# (low, high) seconds, sampled uniformly.
SLIDE_PAUSE = (1.2, 2.0)      # between carousel slides
POST_PAUSE = (3.0, 6.0)       # between posts
SCROLL_PAUSE = (1.5, 2.5)     # between profile scrolls
SCAN_PAUSE = (1.0, 2.0)       # between posts when only reading metadata

# Seconds to let a playing video actually request its file.
VIDEO_SETTLE = 3.0

# Safety rails.
MAX_SLIDES = 25               # carousel slides per post
SCROLL_STAGNANT_LIMIT = 4     # scrolls with no new posts before giving up

BROWSER_VIEWPORT = {"width": 1360, "height": 950}
BROWSER_LOCALE = "en-US"

LOGIN_WAIT_MINUTES = 15
