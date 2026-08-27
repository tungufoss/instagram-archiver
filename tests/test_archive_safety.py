"""Re-running must never destroy an archive.

A real run reported "already have 01.jpg" for nine photographs and left the
folder holding three placeholders: the destination had been written over and
then deleted as a duplicate. `already_archived` is the guard that prevents it.
"""

import hashlib

from instagram_archiver.archive import already_archived

PHOTO = b"pretend this is a jpeg" * 500
DIGEST = hashlib.sha256(PHOTO).hexdigest()


def test_recognises_a_file_we_already_hold(tmp_path):
    dest = tmp_path / "01.jpg"
    dest.write_bytes(PHOTO)
    assert already_archived(dest, {DIGEST}) is True


def test_unknown_content_is_not_treated_as_archived(tmp_path):
    dest = tmp_path / "01.jpg"
    dest.write_bytes(b"something else entirely")
    assert already_archived(dest, {DIGEST}) is False


def test_missing_file_is_not_archived(tmp_path):
    assert already_archived(tmp_path / "nope.jpg", {DIGEST}) is False


def test_empty_index_means_nothing_is_archived(tmp_path):
    dest = tmp_path / "01.jpg"
    dest.write_bytes(PHOTO)
    assert already_archived(dest, set()) is False


def test_a_directory_is_not_a_file(tmp_path):
    (tmp_path / "sub").mkdir()
    assert already_archived(tmp_path / "sub", {DIGEST}) is False


def test_unreadable_path_does_not_raise(tmp_path):
    # A path that cannot be read must answer "no", never explode mid-run.
    assert already_archived(tmp_path / "a" / "b" / "c.jpg", {DIGEST}) is False
