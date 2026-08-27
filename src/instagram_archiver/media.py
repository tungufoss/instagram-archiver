"""Downloading and filing media."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg_tools
from .config import MIN_VIDEO_BYTES


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


def resolve_video(context, urls: list[str], work_dir: Path) -> list[tuple[Path, str]]:
    """Download one slide's video candidates and decide what to keep.

    Normally returns a single (path, source_url). Two only when a slide really
    held two videos and ffprobe confirmed it.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    candidates = []
    for i, url in enumerate(urls):
        tmp = work_dir / f"cand{i:02d}.mp4"
        if fetch(context, url, tmp, MIN_VIDEO_BYTES) is None:
            continue
        candidates.append((tmp, url, tmp.stat().st_size))

    if not candidates:
        return []
    if len(candidates) == 1:
        return [(candidates[0][0], candidates[0][1])]

    probed = [(path, url, ffmpeg_tools.stream_kinds(path)) for path, url, _ in candidates]
    if any(kinds is None for _, _, kinds in probed):
        ffmpeg_tools.warn_missing_once()
        largest = max(candidates, key=lambda c: c[2])
        return [(largest[0], largest[1])]

    with_video = [(p, u, k) for p, u, k in probed if "video" in k]
    audio_only = [(p, u, k) for p, u, k in probed if "video" not in k and "audio" in k]

    # Picture and sound split across two files -> put them back together.
    if len(with_video) == 1 and audio_only and "audio" not in with_video[0][2]:
        merged = work_dir / "merged.mp4"
        if ffmpeg_tools.mux(with_video[0][0], audio_only[0][0], merged):
            return [(merged, with_video[0][1])]
        return [(with_video[0][0], with_video[0][1])]

    if with_video:
        return [(p, u) for p, u, _ in with_video]

    largest = max(candidates, key=lambda c: c[2])
    return [(largest[0], largest[1])]
