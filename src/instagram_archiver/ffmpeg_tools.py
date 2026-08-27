"""Optional ffmpeg integration.

Instagram sometimes delivers one video as two files - picture in one, sound in
the other. When ffmpeg is available we put them back together losslessly.
When it isn't, we keep the larger file and say so.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

_warned = False


def available() -> bool:
    return bool(FFMPEG and FFPROBE)


def stream_kinds(path: Path) -> set[str] | None:
    """Codec types in a media file, e.g. {'video', 'audio'}. None if unknown."""
    if not FFPROBE:
        return None
    try:
        proc = subprocess.run(
            [
                FFPROBE, "-v", "error",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def mux(video_path: Path, audio_path: Path, dest: Path) -> bool:
    """Combine a video-only and an audio-only file without re-encoding."""
    if not FFMPEG:
        return False
    try:
        proc = subprocess.run(
            [
                FFMPEG, "-y", "-v", "error",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c", "copy", "-shortest",
                str(dest),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def warn_missing_once() -> None:
    global _warned
    if _warned:
        return
    _warned = True
    print("  note: ffmpeg/ffprobe not found on PATH. Instagram sometimes serves")
    print("        a video's picture and sound as two separate files; without")
    print("        ffmpeg only the larger one is kept, so that video may end up")
    print("        silent. Install ffmpeg and re-run to fix those.")
