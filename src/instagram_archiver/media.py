"""Downloading and filing media."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg_tools
from .config import AUDIO_SIZE_RATIO, MIN_VIDEO_BYTES


@dataclass
class MediaRecord:
    """One saved file, as it appears in the index."""

    post_url: str
    username: str
    post_id: str
    post_date: str
    media_type: str          # "image" or "video"
    carousel_index: int
    filename: str
    relative_path: str
    source_url: str
    sha256: str


@dataclass
class Candidate:
    """One .mp4 the page requested while a single slide was playing."""

    path: Path
    url: str
    size: int
    kinds: set[str] | None = None    # None when ffprobe is unavailable
    pixels: int = 0                  # 0 when unknown

    @property
    def has_video(self) -> bool:
        return bool(self.kinds) and "video" in self.kinds

    @property
    def has_audio(self) -> bool:
        return bool(self.kinds) and "audio" in self.kinds


def pick_tracks(candidates: list[Candidate]) -> tuple[Candidate | None, Candidate | None]:
    """Choose the picture track, and an audio track only if it is needed.

    One slide plays one video, but Instagram's player may fetch several
    renditions of it at different bitrates, plus a separate audio track. So
    every candidate here describes the *same* video: pick the best rendition
    rather than saving all of them.

    Returns (video, audio); audio is None when the video already has sound or
    when no separate audio track was offered.
    """
    if not candidates:
        return None, None

    # Without ffprobe we cannot tell renditions from tracks. The largest file
    # is the best guess, and resolve_video() warns that sound may be missing.
    if any(c.kinds is None for c in candidates):
        return max(candidates, key=lambda c: c.size), None

    with_video = [c for c in candidates if c.has_video]
    if not with_video:
        return max(candidates, key=lambda c: c.size), None

    # Highest resolution wins; bitrate breaks ties.
    best_video = max(with_video, key=lambda c: (c.pixels, c.size))
    if best_video.has_audio:
        return best_video, None

    audio_only = [c for c in candidates if not c.has_video and c.has_audio]
    if not audio_only:
        return best_video, None

    return best_video, max(audio_only, key=lambda c: c.size)


def fetch(context, url: str, dest: Path, min_bytes: int) -> str | None:
    """Download through the browser context so the logged-in session applies.

    Returns the SHA-256 of the bytes written, or None if nothing usable came
    back.
    """
    try:
        response = context.request.get(url, timeout=120_000)
    except Exception as exc:                       # network, timeout, abort
        print(f"  ! fetch failed for {url[:80]} ({type(exc).__name__})")
        return None
    if not response.ok:
        print(f"  ! HTTP {response.status} for {url[:90]}")
        return None

    data = response.body()
    if len(data) < min_bytes:                      # placeholder / icon / empty
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def content_length(context, url: str) -> int | None:
    """Ask the CDN how big a file is without transferring it."""
    try:
        response = context.request.head(url, timeout=30_000)
    except Exception:
        return None
    if not response.ok:
        return None
    raw = response.headers.get("content-length")
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def plan_downloads(sizes: list[tuple[str, int | None]]) -> list[str]:
    """Pick which candidate URLs are worth actually downloading.

    A player may fetch a dozen renditions of one video plus a separate audio
    track. They are all the same video, so downloading every one wastes
    bandwidth and time. The largest is the best picture; an audio track, when
    present, is far smaller than the video it accompanies. Fetching the largest
    and the smallest covers both cases in two downloads instead of N.
    """
    known = [(url, size) for url, size in sizes if size]
    if not known:
        return [url for url, _ in sizes][:2]      # HEAD unsupported: try a couple

    known.sort(key=lambda item: item[1])
    smallest_url, smallest_size = known[0]
    largest_url, largest_size = known[-1]

    if largest_url == smallest_url:
        return [largest_url]

    # Only worth a second download if the small one could plausibly be an audio
    # track rather than just a lower-bitrate copy of the same picture.
    if smallest_size <= largest_size * AUDIO_SIZE_RATIO:
        return [largest_url, smallest_url]
    return [largest_url]


def resolve_video(context, urls: list[str], work_dir: Path) -> list[tuple[Path, str]]:
    """Download one slide's candidates and return the single file to keep.

    Returns [] when nothing usable came back, otherwise exactly one
    (path, source_url).
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    wanted = plan_downloads([(url, content_length(context, url)) for url in urls])
    skipped = len(urls) - len(wanted)
    if skipped > 0:
        print(f"    ({len(urls)} renditions offered, fetching {len(wanted)})")

    candidates: list[Candidate] = []
    for i, url in enumerate(wanted):
        tmp = work_dir / f"cand{i:02d}.mp4"
        if fetch(context, url, tmp, MIN_VIDEO_BYTES) is None:
            continue
        probed = ffmpeg_tools.probe(tmp)
        candidates.append(
            Candidate(
                path=tmp,
                url=url,
                size=tmp.stat().st_size,
                kinds=probed[0] if probed else None,
                pixels=probed[1] if probed else 0,
            )
        )

    if not candidates:
        return []

    if any(c.kinds is None for c in candidates) and len(candidates) > 1:
        ffmpeg_tools.warn_missing_once()

    video, audio = pick_tracks(candidates)
    if video is None:
        return []

    # Picture and sound arrived separately: put them back together.
    if audio is not None:
        merged = work_dir / "merged.mp4"
        if ffmpeg_tools.mux(video.path, audio.path, merged):
            return [(merged, video.url)]

    return [(video.path, video.url)]
