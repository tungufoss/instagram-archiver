"""A download is judged by what it is, not how big it is.

A real four-second reel came back at 44 KB and was discarded by a 50 KB
floor. The post vanished from the archive and nothing said why.
"""

from instagram_archiver.media import looks_like_media

PAD = b"x" * 4000


def test_the_44kb_reel_that_was_being_discarded():
    mp4 = b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"x" * 44_000
    assert looks_like_media(mp4) is True


def test_recognises_the_formats_instagram_serves():
    assert looks_like_media(b"\xff\xd8\xff\xe0" + PAD) is True        # jpeg
    assert looks_like_media(b"\x89PNG\r\n\x1a\n" + PAD) is True       # png
    assert looks_like_media(b"RIFF" + PAD) is True                    # webp
    assert looks_like_media(b"\x00\x00\x00 ftypmp42" + PAD) is True   # mp4


def test_rejects_an_error_page():
    assert looks_like_media(b"<!DOCTYPE html><html>" + PAD) is False


def test_rejects_an_empty_or_tiny_response():
    assert looks_like_media(b"") is False
    assert looks_like_media(b"nope") is False


def test_rejects_padding_that_is_big_but_not_media():
    assert looks_like_media(b"z" * 500_000) is False


def test_a_small_but_real_file_is_kept():
    """The point of the change: 2 KB of genuine jpeg is a photograph."""
    assert looks_like_media(b"\xff\xd8\xff\xe0" + b"y" * 1500) is True
