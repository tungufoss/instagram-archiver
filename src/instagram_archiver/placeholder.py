"""A stand-in image marking a video that was not saved.

Without this, `--skip-videos` leaves a silent gap: the numbering jumps and
nothing records that a video was ever in that slot. A placeholder keeps the
carousel positions honest and shows up in a photo browser exactly where the
missing video belongs.

The PNG is written by hand rather than through Pillow or ffmpeg, so a
placeholder never depends on something being installed.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

WIDTH = 640
HEIGHT = 360

# Dark grey field with a lighter border, so it reads as deliberate rather than
# as a corrupt file.
BACKGROUND = (38, 38, 42)
BORDER = (120, 120, 130)
BORDER_WIDTH = 6

SUFFIX = ".video-not-saved.png"


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def _pixels(width: int, height: int) -> bytes:
    rows = bytearray()
    for y in range(height):
        rows.append(0)                              # PNG filter type: none
        for x in range(width):
            edge = (
                x < BORDER_WIDTH
                or y < BORDER_WIDTH
                or x >= width - BORDER_WIDTH
                or y >= height - BORDER_WIDTH
            )
            rows.extend(BORDER if edge else BACKGROUND)
    return bytes(rows)


def write(path: Path, width: int = WIDTH, height: int = HEIGHT) -> None:
    """Write a placeholder PNG to `path`."""
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(_pixels(width, height), 9))
        + _chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
