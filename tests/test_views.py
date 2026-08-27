"""Play counts, read from the tiles on a profile's reels tab.

Instagram leaves `view_count` null in every post's page data - for viewers and
for the account itself - but draws the number on each reel tile.
"""

from instagram_archiver.views import code_of, from_tiles, parse_count


def test_reads_the_numbers_as_drawn():
    assert parse_count("2,653") == 2653
    assert parse_count("686") == 686
    assert parse_count(" 1,207 ") == 1207


def test_reads_abbreviated_counts():
    assert parse_count("1.2M") == 1_200_000
    assert parse_count("12K") == 12_000


def test_ignores_anything_that_is_not_a_count():
    for text in ("", "Boost reel", "View insights", "abc", None):
        assert parse_count(text) is None


def test_pairs_a_reel_with_its_count():
    tiles = [{"href": "/someaccount/reel/ABC123/", "text": "2,653"}]
    assert from_tiles(tiles) == {"ABC123": 2653}


def test_a_tile_with_no_number_is_left_out():
    """No count shown means no count recorded, not a zero."""
    tiles = [{"href": "/someaccount/reel/ABC123/", "text": ""},
             {"href": "/someaccount/reel/DEF456/", "text": "42"}]
    assert from_tiles(tiles) == {"DEF456": 42}


def test_non_reel_links_are_ignored():
    tiles = [{"href": "/someaccount/p/ABC123/", "text": "99"}]
    assert from_tiles(tiles) == {}


def test_code_extraction():
    assert code_of("/someaccount/reel/AB-c_1/") == "AB-c_1"
    assert code_of("https://www.instagram.com/reel/XYZ/") == "XYZ"
    assert code_of("/someaccount/p/ABC/") is None
    assert code_of("") is None


def test_empty_input():
    assert from_tiles([]) == {}
    assert from_tiles(None) == {}
