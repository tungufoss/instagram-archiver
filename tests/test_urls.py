"""URL helpers. No browser needed."""

import pytest

from instagram_archiver.urls import (
    clean_video_url,
    image_extension,
    image_key,
    is_video_request,
    normalise_post_url,
    post_id_from,
    username_from_profile_url,
    video_key,
)


@pytest.mark.parametrize(
    "href,expected",
    [
        ("/p/ABC123/", "https://www.instagram.com/p/ABC123/"),
        ("/p/ABC-12_x/?img_index=3", "https://www.instagram.com/p/ABC-12_x/"),
        ("https://www.instagram.com/reel/XYZ789/", "https://www.instagram.com/reel/XYZ789/"),
        ("/someaccount/", None),
        ("/explore/", None),
        ("#", None),
        ("", None),
    ],
)
def test_normalise_post_url(href, expected):
    assert normalise_post_url(href) == expected


def test_post_id_from():
    assert post_id_from("https://www.instagram.com/p/ABC123/") == "ABC123"
    assert post_id_from("https://www.instagram.com/reel/XYZ/") == "XYZ"
    assert post_id_from("https://www.instagram.com/someaccount/") == "unknown"


def test_image_key_ignores_size_variants():
    base = "https://scontent.cdninstagram.com/v/t51.29350-15/12345_n.jpg"
    assert image_key(base + "?stp=dst-jpg_e35_s640x640") == "12345_n"
    assert image_key(base + "?stp=dst-jpg_e35_s1080x1080") == "12345_n"


def test_image_extension():
    assert image_extension("https://x/y/a_n.webp?q=1") == ".webp"
    assert image_extension("https://x/y/a_n.jpg") == ".jpg"
    assert image_extension("https://x/y/noextension?q=1") == ".jpg"
    assert image_extension("https://x/y/a_n.heic") == ".jpg"  # not kept as-is


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://scontent.cdninstagram.com/o1/v/t16/f1/ABC_n.mp4?efg=x", True),
        ("https://video.xx.fbcdn.net/v/ABC_n.mp4", True),
        ("https://scontent.cdninstagram.com/v/t51/123_n.jpg", False),
        ("https://evil.example.com/payload.mp4", False),
    ],
)
def test_is_video_request(url, expected):
    assert is_video_request(url) is expected


def test_clean_video_url_strips_byte_ranges():
    url = (
        "https://scontent.cdninstagram.com/o1/v/t16/ABC_n.mp4"
        "?efg=xyz&bytestart=0&byteend=99999&_nc_ht=h"
    )
    cleaned = clean_video_url(url)
    assert "bytestart" not in cleaned
    assert "byteend" not in cleaned
    assert "efg=xyz" in cleaned and "_nc_ht=h" in cleaned


def test_video_key_matches_across_ranges():
    a = "https://scontent.cdninstagram.com/o1/v/ABC_n.mp4?bytestart=0&byteend=100"
    b = "https://scontent.cdninstagram.com/o1/v/ABC_n.mp4?bytestart=101&byteend=200"
    assert video_key(a) == video_key(b) == "ABC_n.mp4"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.instagram.com/someone/", "someone"),
        ("https://www.instagram.com/someone", "someone"),
        ("https://www.instagram.com/someone/?hl=en", "someone"),
        ("https://www.instagram.com/some.one_2020/reels/", "some.one_2020"),
        ("https://www.instagram.com/p/ABC123/", None),
        ("https://www.instagram.com/explore/", None),
        ("https://www.instagram.com/", None),
        ("", None),
    ],
)
def test_username_from_profile_url(url, expected):
    assert username_from_profile_url(url) == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        ("https://www.instagram.com/reel/ABC123/", "https://www.instagram.com/p/ABC123/"),
        ("https://www.instagram.com/p/ABC123/", "https://www.instagram.com/p/ABC123/"),
        ("/reel/ABC-1_2/", "https://www.instagram.com/p/ABC-1_2/"),
    ],
)
def test_page_url_for_prefers_the_post_form(given, expected):
    """A reel page omits the embedded media list; /p/ carries it."""
    from instagram_archiver.urls import page_url_for
    assert page_url_for(given) == expected


def test_page_url_for_leaves_other_urls_alone():
    from instagram_archiver.urls import page_url_for
    assert page_url_for("https://example.com/x") == "https://example.com/x"
