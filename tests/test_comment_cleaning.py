"""Turning a rendered comment block into a comment.

Instagram does not put comments in the page JSON - a post with four thousand
of them reports `preview_comments: []` - so they are read from the DOM, which
means the surrounding interface comes along and has to be stripped.
"""

from instagram_archiver.comments import clean_block, from_blocks


def block(*lines):
    return "\n".join(lines)


def test_strips_the_interface_around_a_comment():
    raw = block("someone", "7w", "Lovely photos", "3 likes", "Reply",
                "View all 3 replies")
    assert clean_block("someone", raw) == "Lovely photos"


def test_keeps_a_multi_line_comment():
    raw = block("someone", "2w", "First line", "second line", "12 likes", "Reply")
    assert clean_block("someone", raw) == "First line\nsecond line"


def test_relative_ages_are_not_text():
    for age in ("7w", "10h", "3d", "45m", "2 hours ago"):
        assert clean_block("someone", block("someone", age, "hi")) == "hi"


def test_like_counts_are_not_text():
    raw = block("someone", "1w", "hi", "1 like")
    assert clean_block("someone", raw) == "hi"
    raw = block("someone", "1w", "hi", "1,234 likes")
    assert clean_block("someone", raw) == "hi"


def test_a_comment_that_is_only_furniture_yields_nothing():
    assert clean_block("someone", block("someone", "7w", "Reply")) == ""


# --- assembling rows -------------------------------------------------------


def raw(username, dt, *lines):
    return {"username": username, "datetime": dt, "block": block(*lines)}


def test_builds_rows():
    got = from_blocks([raw("someone", "2026-06-17T19:04:32.000Z",
                           "someone", "7w", "Nice", "3 likes", "Reply")])
    assert len(got) == 1
    assert got[0].username == "someone"
    assert got[0].timestamp == "2026-06-17T19:04:32.000Z"
    assert got[0].text == "Nice"


def test_the_posts_own_caption_is_not_a_comment():
    """The caption sits in the same shape: author, time, text."""
    stamp = "2026-06-08T10:00:00.000Z"
    rows = from_blocks(
        [raw("theauthor", stamp, "theauthor", "11w", "A day at the museum"),
         raw("someone", "2026-06-17T19:04:32.000Z", "someone", "7w", "Lovely")],
        caption="A day at the museum",
        post_timestamp=stamp,
    )
    assert [r.username for r in rows] == ["someone"]


def test_caption_excluded_by_text_even_without_a_timestamp():
    rows = from_blocks(
        [raw("theauthor", "", "theauthor", "11w", "A day at the museum")],
        caption="A day at the museum",
    )
    assert rows == []


def test_duplicates_are_collapsed():
    one = raw("someone", "2026-06-17T19:04:32.000Z", "someone", "7w", "Nice")
    assert len(from_blocks([one, one])) == 1


def test_empty_input():
    assert from_blocks([]) == []
    assert from_blocks(None) == []
