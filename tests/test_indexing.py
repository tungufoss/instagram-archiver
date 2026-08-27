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


def test_a_real_file_supersedes_its_placeholder(tmp_path):
    """Filling in a skipped video must not leave the placeholder row behind."""
    placeholder = MediaRecord(
        post_url="https://www.instagram.com/p/P1/", username="someaccount",
        post_id="P1", post_date="2026-06-08", media_type="video_skipped",
        carousel_index=4, filename="04.video-not-saved.png",
        relative_path="someaccount/2026-06-08_P1/04.video-not-saved.png",
        source_url="", sha256="",
    )
    write_index(tmp_path, [placeholder])
    assert len(json.loads((tmp_path / "index.json").read_text())) == 1

    real = MediaRecord(
        post_url="https://www.instagram.com/p/P1/", username="someaccount",
        post_id="P1", post_date="2026-06-08", media_type="video",
        carousel_index=4, filename="04.mp4",
        relative_path="someaccount/2026-06-08_P1/04.mp4",
        source_url="https://cdn/v.mp4", sha256="dd",
    )
    write_index(tmp_path, [real])

    rows = json.loads((tmp_path / "index.json").read_text())
    assert len(rows) == 1, "the placeholder row should be gone"
    assert rows[0]["media_type"] == "video"
    assert rows[0]["filename"] == "04.mp4"


def test_placeholders_at_other_positions_survive(tmp_path):
    def ph(index):
        return MediaRecord(
            post_url="https://www.instagram.com/p/P1/", username="someaccount",
            post_id="P1", post_date="2026-06-08", media_type="video_skipped",
            carousel_index=index, filename=f"{index:02d}.video-not-saved.png",
            relative_path=f"someaccount/2026-06-08_P1/{index:02d}.video-not-saved.png",
            source_url="", sha256="",
        )
    write_index(tmp_path, [ph(4), ph(6), ph(8)])

    real = MediaRecord(
        post_url="https://www.instagram.com/p/P1/", username="someaccount",
        post_id="P1", post_date="2026-06-08", media_type="video",
        carousel_index=6, filename="06.mp4",
        relative_path="someaccount/2026-06-08_P1/06.mp4",
        source_url="https://cdn/v.mp4", sha256="dd",
    )
    write_index(tmp_path, [real])

    rows = json.loads((tmp_path / "index.json").read_text())
    kinds = {r["carousel_index"]: r["media_type"] for r in rows}
    assert kinds == {4: "video_skipped", 6: "video", 8: "video_skipped"}
