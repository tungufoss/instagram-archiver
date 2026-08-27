"""Reading and recording comments.

Off by default: they are other people's words about someone's post, so
collecting them should be a deliberate choice rather than a side effect.
"""

import json

from instagram_archiver.embedded import parse_post
from instagram_archiver.indexing import write_comments

CODE = "ABC123"


def post_with(comments):
    return json.dumps({
        "code": CODE,
        "image_versions2": {"candidates": [{"width": 1440, "height": 1080}]},
        "comments": comments,
    })


def test_reads_username_time_and_text():
    block = post_with([
        {"user": {"username": "someone"}, "created_at": 1770000000,
         "text": "  Lovely photos  "},
    ])
    got = parse_post([block], CODE).comments
    assert len(got) == 1
    assert got[0].username == "someone"
    assert got[0].text == "Lovely photos"
    assert got[0].timestamp.startswith("2026-")


def test_handles_the_owner_shape():
    """Instagram has used `owner` as well as `user`."""
    block = post_with([{"owner": {"username": "other"}, "created_at": 1770000000,
                        "text": "hi"}])
    assert parse_post([block], CODE).comments[0].username == "other"


def test_comments_without_text_are_dropped():
    block = post_with([
        {"user": {"username": "a"}, "created_at": 1770000000, "text": "   "},
        {"user": {"username": "b"}, "created_at": 1770000000},
    ])
    assert parse_post([block], CODE).comments == []


def test_missing_timestamp_is_empty_not_wrong():
    block = post_with([{"user": {"username": "a"}, "text": "hello"}])
    assert parse_post([block], CODE).comments[0].timestamp == ""


def test_no_comments_key_is_fine():
    block = json.dumps({"code": CODE,
                        "image_versions2": {"candidates": [{"width": 1, "height": 1}]}})
    assert parse_post([block], CODE).comments == []


def test_order_is_preserved():
    block = post_with([
        {"user": {"username": "first"}, "created_at": 1, "text": "one"},
        {"user": {"username": "second"}, "created_at": 2, "text": "two"},
    ])
    assert [c.username for c in parse_post([block], CODE).comments] == [
        "first", "second"]


# --- writing them out ------------------------------------------------------


def row(username="someone", text="nice", timestamp="2026-06-08T10:00:00+00:00"):
    return {"post_url": "https://www.instagram.com/p/ABC/", "post_id": "ABC",
            "post_date": "2026-06-08", "username": username,
            "timestamp": timestamp, "text": text}


def test_writes_both_files(tmp_path):
    assert write_comments(tmp_path, [row()]) == 1
    assert (tmp_path / "comments.json").exists()
    assert (tmp_path / "comments.csv").exists()


def test_rerunning_does_not_duplicate(tmp_path):
    write_comments(tmp_path, [row()])
    assert write_comments(tmp_path, [row()]) == 0
    rows = json.loads((tmp_path / "comments.json").read_text(encoding="utf-8"))
    assert len(rows) == 1


def test_a_second_comment_is_appended(tmp_path):
    write_comments(tmp_path, [row(text="one")])
    assert write_comments(tmp_path, [row(text="two")]) == 1
    rows = json.loads((tmp_path / "comments.json").read_text(encoding="utf-8"))
    assert {r["text"] for r in rows} == {"one", "two"}


def test_same_words_from_different_people_both_kept(tmp_path):
    write_comments(tmp_path, [row(username="a", text="nice")])
    assert write_comments(tmp_path, [row(username="b", text="nice")]) == 1


def test_nothing_to_write(tmp_path):
    assert write_comments(tmp_path, []) == 0
    assert not (tmp_path / "comments.json").exists()
