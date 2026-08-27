"""Working out where each file belongs under a given layout."""

from pathlib import Path

from instagram_archiver.relayout import desired_path

OUT = Path("/archive")


def row(filename="01.jpg", post_url="https://www.instagram.com/p/ABC/"):
    return {
        "username": "someaccount",
        "post_id": "ABC",
        "post_date": "2026-06-08",
        "filename": filename,
        "post_url": post_url,
        "relative_path": "someaccount/2026-06-08_ABC/01.jpg",
    }


def test_flat_layout():
    got = desired_path(OUT, row(), flatten=True)
    assert got == OUT / "someaccount" / "2026-06-08_ABC_01.jpg"


def test_nested_layout():
    got = desired_path(OUT, row(), flatten=False)
    assert got == OUT / "someaccount" / "2026-06-08_ABC" / "01.jpg"


def test_flat_name_is_not_prefixed_twice():
    """Re-flattening an already flat archive must be a no-op."""
    already = row(filename="2026-06-08_ABC_01.jpg")
    assert desired_path(OUT, already, flatten=True) == (
        OUT / "someaccount" / "2026-06-08_ABC_01.jpg"
    )


def test_unflattening_strips_the_prefix():
    already = row(filename="2026-06-08_ABC_01.jpg")
    assert desired_path(OUT, already, flatten=False) == (
        OUT / "someaccount" / "2026-06-08_ABC" / "01.jpg"
    )


def test_placeholders_keep_their_compound_suffix():
    got = desired_path(OUT, row(filename="04.video-not-saved.png"), flatten=True)
    assert got.name == "2026-06-08_ABC_04.video-not-saved.png"


def test_a_reel_sits_beside_the_other_posts():
    """A reel is an ordinary post of the account's, not a separate category."""
    reel = row(post_url="https://www.instagram.com/reel/XYZ/")
    got = desired_path(OUT, reel, flatten=True)
    assert got == OUT / "someaccount" / "2026-06-08_ABC_01.jpg"


def test_incomplete_row_is_ignored():
    assert desired_path(OUT, {"username": "someaccount"}, flatten=True) is None
