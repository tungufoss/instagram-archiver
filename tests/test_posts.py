"""Post-level metadata: one row per post, per account."""

import csv
import json

from instagram_archiver.posts import PostRecord, summarise, write_posts


def record(post_id="ABC", username="someaccount", kind="post", likes=10,
           comments=2, images=3, videos=1, date="2026-06-08", caption="hello"):
    return PostRecord(
        post_url=f"https://www.instagram.com/p/{post_id}/",
        post_id=post_id, username=username, post_date=date,
        post_time=f"{date}T10:00:00.000Z", kind=kind, likes=likes, views=None,
        comments=comments, images=images, videos=videos,
        media_count=images + videos, caption=caption,
    )


def test_writes_into_the_account_folder(tmp_path):
    write_posts(tmp_path, [record()])
    assert (tmp_path / "someaccount" / "posts.json").exists()
    assert (tmp_path / "someaccount" / "posts.csv").exists()
    assert not (tmp_path / "posts.json").exists()


def test_two_accounts_do_not_mix(tmp_path):
    write_posts(tmp_path, [record(post_id="A", username="one"),
                           record(post_id="B", username="two")])
    one = json.loads((tmp_path / "one" / "posts.json").read_text(encoding="utf-8"))
    two = json.loads((tmp_path / "two" / "posts.json").read_text(encoding="utf-8"))
    assert [r["post_id"] for r in one] == ["A"]
    assert [r["post_id"] for r in two] == ["B"]


def test_rescanning_updates_rather_than_duplicates(tmp_path):
    write_posts(tmp_path, [record(likes=10)])
    write_posts(tmp_path, [record(likes=25)])
    rows = json.loads((tmp_path / "someaccount" / "posts.json").read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["likes"] == 25, "a later scan should refresh the counts"


def test_newest_first(tmp_path):
    write_posts(tmp_path, [record(post_id="OLD", date="2025-01-01"),
                           record(post_id="NEW", date="2026-06-08")])
    rows = json.loads((tmp_path / "someaccount" / "posts.json").read_text(encoding="utf-8"))
    assert [r["post_id"] for r in rows] == ["NEW", "OLD"]


def test_csv_has_the_columns(tmp_path):
    write_posts(tmp_path, [record()])
    with (tmp_path / "someaccount" / "posts.csv").open(encoding="utf-8-sig", newline="") as fh:
        row = next(csv.DictReader(fh))
    for column in ("post_url", "post_date", "kind", "likes", "comments",
                   "images", "videos", "caption"):
        assert column in row


def test_summary_totals():
    totals = summarise([
        record(post_id="A", kind="post", likes=10, comments=2, images=3, videos=1),
        record(post_id="B", kind="reel", likes=5, comments=0, images=0, videos=1),
    ])
    assert totals["posts"] == 2
    assert totals["reels"] == 1
    assert totals["images"] == 3
    assert totals["videos"] == 2
    assert totals["likes"] == 15
    assert totals["views"] == "not shown"
    assert totals["comments"] == 2


def test_nothing_to_write(tmp_path):
    assert write_posts(tmp_path, []) == []
