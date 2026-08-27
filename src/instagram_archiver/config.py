"""Tunable constants.

Pacing is deliberately conservative: this tool browses like a person, and
nothing here should be raised to hammer Instagram.
"""

from __future__ import annotations

# Hosts that serve Instagram media. Used to ignore unrelated requests.
CDN_HOSTS = ("cdninstagram", "fbcdn")

# A response has to be at least this big to be a file rather than an error
# page, but size alone decides nothing: what a download is gets settled by its
# leading bytes. See media.looks_like_media - a real 44 KB reel was once
# thrown away by a 50 KB floor, which lost the post and said nothing.
MIN_MEDIA_BYTES = 1_024

# Kept for the video candidate sizing, which compares renditions rather than
# judging whether a download is real.
MIN_IMAGE_BYTES = MIN_MEDIA_BYTES
MIN_VIDEO_BYTES = MIN_MEDIA_BYTES

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

# How long to wait for the first slide to acquire a size. A video can take
# several seconds, and treating that as an empty post loses it silently.
FIRST_SLIDE_TIMEOUT = 15.0

# Seconds to let a playing video actually request its file.
VIDEO_SETTLE = 3.0

# Safety rails.
MAX_SLIDES = 25               # carousel slides per post
SCROLL_STAGNANT_LIMIT = 4     # scrolls with no new posts before giving up

BROWSER_VIEWPORT = {"width": 1360, "height": 950}
BROWSER_LOCALE = "en-US"

LOGIN_WAIT_MINUTES = 15
