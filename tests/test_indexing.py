"""Index writing, merging and dedup memory."""

import csv
import json

from instagram_archiver.indexing import load_known_hashes, write_index
from instagram_archiver.media import MediaRecord


def record(post_id="P1", sha="aa", index=1, media_type="image", filename="01.jpg",
           username="someaccount"):
    return MediaRecord(
        post_url=f"https://www.instagram.com/p/{post_id}/",
        username=username,
        post_id=post_id,
        post_date="2026-08-25",
        media_type=media_type,
        carousel_index=index,
        filename=filename,
        relative_path=f"{username}/2026-08-25_{post_id}/{filename}",
        source_url="https://scontent.cdninstagram.com/x",
        sha256=sha,
    )


def test_write_and_reload(tmp_path):
    records = [
        record(sha="aa"),
        record(sha="bb", index=2, media_type="video", filename="02.mp4"),
    ]
    write_index(tmp_path, records)

    assert load_known_hashes(tmp_path) == {"aa", "bb"}
    rows = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [r["media_type"] for r in rows] == ["image", "video"]


def test_rerun_does_not_duplicate(tmp_path):
    records = [record(sha="aa")]
    write_index(tmp_path, records)
    write_index(tmp_path, records)

    rows = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(rows) == 1


def test_legacy_rows_without_new_columns_survive(tmp_path):
    """An index written before media_type existed must still merge cleanly."""
    legacy = [
        {
            "post_url": "u",
            "post_id": "P0",
            "post_date": "2026-08-01",
            "carousel_index": 1,
            "filename": "01.jpg",
            "relative_path": "a/01.jpg",
            "source_url": "http://o",
            "sha256": "zz",
        }
    ]
    (tmp_path / "index.json").write_text(json.dumps(legacy), encoding="utf-8")

    write_index(tmp_path, [record(sha="aa")])

    assert load_known_hashes(tmp_path) == {"zz", "aa"}
    with (tmp_path / "index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert "media_type" in rows[0]
    assert rows[0]["media_type"] == ""       # legacy row, column left blank
    assert rows[1]["media_type"] == "image"


def test_corrupt_index_is_not_fatal(tmp_path):
    (tmp_path / "index.json").write_text("{ not json", encoding="utf-8")
    assert load_known_hashes(tmp_path) == set()
    write_index(tmp_path, [record(sha="aa")])
    assert load_known_hashes(tmp_path) == {"aa"}


def test_empty_records_writes_nothing(tmp_path):
    write_index(tmp_path, [])
    assert not (tmp_path / "index.json").exists()
