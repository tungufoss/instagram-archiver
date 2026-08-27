"""Follower snapshots and what changed between them."""

import csv
import json
from datetime import datetime, timezone

from instagram_archiver.followers import (
    TIMESERIES_CSV,
    compare,
    previous_snapshot,
    write_snapshot,
)

WHEN = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def test_first_snapshot_has_no_departures(tmp_path):
    _, change = write_snapshot(tmp_path, "someaccount", ["a", "b"], WHEN)
    assert change.joined == ["a", "b"]
    assert change.left == []


def test_second_snapshot_reports_the_difference(tmp_path):
    write_snapshot(tmp_path, "someaccount", ["a", "b", "c"], WHEN)
    _, change = write_snapshot(tmp_path, "someaccount", ["b", "c", "d"], LATER)
    assert change.joined == ["d"]
    assert change.left == ["a"]


def test_no_change_is_quiet(tmp_path):
    write_snapshot(tmp_path, "someaccount", ["a", "b"], WHEN)
    _, change = write_snapshot(tmp_path, "someaccount", ["b", "a"], LATER)
    assert change.quiet


def test_snapshot_records_the_names(tmp_path):
    path, _ = write_snapshot(tmp_path, "someaccount", ["zoe", "amy"], WHEN)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["account"] == "someaccount"
    assert data["count"] == 2
    assert data["followers"] == ["amy", "zoe"], "sorted, so diffs read cleanly"


def test_timeseries_grows_one_row_per_run(tmp_path):
    write_snapshot(tmp_path, "someaccount", ["a"], WHEN)
    write_snapshot(tmp_path, "someaccount", ["a", "b"], LATER)

    with (tmp_path / TIMESERIES_CSV).open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["count"] for r in rows] == ["1", "2"]
    assert rows[1]["joined"] == "b"
    assert rows[1]["left"] == ""


def test_previous_snapshot_reads_the_latest(tmp_path):
    write_snapshot(tmp_path, "someaccount", ["a"], WHEN)
    write_snapshot(tmp_path, "someaccount", ["a", "b"], LATER)
    assert previous_snapshot(tmp_path)[0] == ["a", "b"]


def test_previous_snapshot_when_there_is_none(tmp_path):
    assert previous_snapshot(tmp_path)[0] == []


def test_compare_is_order_insensitive():
    assert compare(["b", "a"], ["a", "b"]).quiet


# --- partial snapshots must not invent departures -------------------------


def test_a_partial_snapshot_is_marked_incomplete(tmp_path):
    import json as _json
    path, _ = write_snapshot(tmp_path, "someaccount", ["a", "b"], WHEN, stated=10)
    data = _json.loads(path.read_text(encoding="utf-8"))
    assert data["complete"] is False
    assert data["stated_count"] == 10


def test_a_full_snapshot_is_marked_complete(tmp_path):
    import json as _json
    path, _ = write_snapshot(tmp_path, "someaccount", ["a", "b"], WHEN, stated=2)
    assert _json.loads(path.read_text(encoding="utf-8"))["complete"] is True


def test_comparison_is_unreliable_when_a_snapshot_was_partial(tmp_path):
    """453 of 603 one run and 456 the next would invent dozens of departures."""
    write_snapshot(tmp_path, "someaccount", ["a", "b", "c"], WHEN, stated=10)
    _, change = write_snapshot(tmp_path, "someaccount", ["a", "b"], LATER,
                               stated=10)
    assert change.reliable is False


def test_comparison_is_reliable_when_both_were_complete(tmp_path):
    write_snapshot(tmp_path, "someaccount", ["a", "b"], WHEN, stated=2)
    _, change = write_snapshot(tmp_path, "someaccount", ["a"], LATER, stated=1)
    assert change.reliable is True
    assert change.left == ["b"]


def test_timeseries_records_completeness(tmp_path):
    import csv as _csv
    write_snapshot(tmp_path, "someaccount", ["a"], WHEN, stated=5)
    with (tmp_path / TIMESERIES_CSV).open(encoding="utf-8", newline="") as fh:
        row = next(_csv.DictReader(fh))
    assert row["stated_count"] == "5"
    assert row["complete"] == "False"
