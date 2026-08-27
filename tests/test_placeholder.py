"""The stand-in image for a video that was not saved."""

import struct

from instagram_archiver import placeholder


def test_writes_a_valid_png(tmp_path):
    dest = tmp_path / f"04{placeholder.SUFFIX}"
    placeholder.write(dest)
    data = dest.read_bytes()

    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    assert data[-8:-4] == b"IEND"


def test_dimensions_are_recorded_in_the_header(tmp_path):
    dest = tmp_path / "x.png"
    placeholder.write(dest, width=320, height=180)
    width, height = struct.unpack(">II", dest.read_bytes()[16:24])
    assert (width, height) == (320, 180)


def test_filename_says_what_happened(tmp_path):
    dest = tmp_path / f"04{placeholder.SUFFIX}"
    placeholder.write(dest)
    assert "video-not-saved" in dest.name
    assert dest.suffix == ".png"


def test_creates_missing_directories(tmp_path):
    dest = tmp_path / "a" / "b" / f"01{placeholder.SUFFIX}"
    placeholder.write(dest)
    assert dest.exists()


def test_small_enough_to_be_obviously_not_a_photo(tmp_path):
    dest = tmp_path / "x.png"
    placeholder.write(dest)
    assert dest.stat().st_size < 20_000
