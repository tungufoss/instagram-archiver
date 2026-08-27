"""og:description parsing.

The real-world sample here is the shape Instagram serves for a reel, which
renders no <time> element and surrounds the media with advertiser links.
"""

import pytest

from instagram_archiver.metadata import parse_og_description

REEL_SAMPLE = (
    '628K likes, 4,110 comments - kendalljenner on April 1, 2026: '
    '"favorite lip combo @lorealparis #lorealparispartner". '
)


def test_reel_sample():
    username, date = parse_og_description(REEL_SAMPLE)
    assert username == "kendalljenner"
    assert date == "2026-04-01"


@pytest.mark.parametrize(
    "text,username,date",
    [
        ('12 likes, 0 comments - some.account_1 on December 25, 2024: "hi".',
         "some.account_1", "2024-12-25"),
        ('1 like - a_b.c on January 1, 2020: "x"', "a_b.c", "2020-01-01"),
        # Author present, date missing or unparseable.
        ("5 likes - someone on Funday 99, 1234: \"x\"", "someone", None),
        # Nothing usable.
        ("Instagram", None, None),
        ("", None, None),
        (None, None, None),
    ],
)
def test_variants(text, username, date):
    assert parse_og_description(text) == (username, date)


def test_caption_containing_similar_text_does_not_win():
    """The first ' - user on Month D, YYYY:' is the real author line."""
    text = (
        '10 likes, 2 comments - realauthor on March 3, 2026: '
        '"quoting - someoneelse on April 4, 2020: hello".'
    )
    assert parse_og_description(text) == ("realauthor", "2026-03-03")
