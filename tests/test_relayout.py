"""Changing the output layout must move files, not download them again."""

import json

from instagram_archiver.archive import prune_empty_dirs
from instagram_archiver.indexing import load_archived_files, write_index
from instagram_archiver.media import MediaRecord


def record(post_id="ABC", index=1, filename="01.jpg", rel=None, sha="aa"):
    return MediaRecord(
        post_url=f"https://www.instagram.com/p/{post_id}/",
        username="someaccount",
        post_id=post_id,
        post_date="2026-06-08",
        media_type="image",
        carousel_index=index,
        filename=filename,
        relative_path=rel or f"someaccount/2026-06-08_{post_id}/{filename}",
        source_url="https://cdn/x.jpg",
        sha256=sha,
    )


def test_finds_files_we_already_hold(tmp_path):
    dest = tmp_path / "someaccount" / "2026-06-08_ABC" / "01.jpg"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"photo")
    write_index(tmp_path, [record()])

    held = load_archived_files(tmp_path)
    assert held[("ABC", 1)] == dest


def test_rows_whose_file_has_gone_are_ignored(tmp_path):
    write_index(tmp_path, [record()])          # nothing written to disk
    assert load_archived_files(tmp_path) == {}


def test_moving_a_file_updates_its_recorded_path(tmp_path):
    """A relocated file needs its path corrected, not a duplicate row."""
    write_index(tmp_path, [record()])
    flat = "someaccount/2026-06-08_ABC_01.jpg"
    write_index(tmp_path, [record(rel=flat, filename="2026-06-08_ABC_01.jpg")])

    rows = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(rows) == 1, "the same content must not appear twice"
    assert rows[0]["relative_path"] == flat


def test_prune_removes_folders_emptied_by_a_move(tmp_path):
    nested = tmp_path / "someaccount" / "2026-06-08_ABC"
    nested.mkdir(parents=True)
    (tmp_path / "someaccount" / "2026-06-08_ABC_01.jpg").write_bytes(b"moved here")

    assert prune_empty_dirs(tmp_path) == (1, 0)
    assert not nested.exists()
    assert (tmp_path / "someaccount").exists(), "a folder with files stays"


def test_prune_leaves_a_populated_tree_alone(tmp_path):
    keep = tmp_path / "someaccount" / "2026-06-08_ABC"
    keep.mkdir(parents=True)
    (keep / "01.jpg").write_bytes(b"photo")
    assert prune_empty_dirs(tmp_path) == (0, 0)
    assert (keep / "01.jpg").exists()


def test_prune_on_a_missing_directory_is_harmless():
    from pathlib import Path
    assert prune_empty_dirs(Path("no-such-directory-here")) == (0, 0)
