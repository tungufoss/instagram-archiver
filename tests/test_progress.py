"""The progress line. Pure formatting, no clock of its own in tests."""

from instagram_archiver.progress import bar, line


def test_bar_endpoints():
    assert bar(0, 10, width=10) == "." * 10
    assert bar(10, 10, width=10) == "#" * 10
    assert bar(5, 10, width=10) == "#####....."


def test_bar_handles_zero_total():
    assert bar(0, 0, width=6) == "------"


def test_line_shows_counts_and_eta():
    text = line(done=12, total=45, files=148, started=0.0, now=552.0)
    assert "12/45 posts" in text
    assert "148 files" in text
    assert "09:12 elapsed" in text
    assert "left" in text


def test_no_eta_before_first_post():
    assert "left" not in line(done=0, total=45, files=0, started=0.0, now=3.0)


def test_no_eta_when_finished():
    assert "left" not in line(done=45, total=45, files=501, started=0.0, now=1980.0)


def test_eta_is_linear_extrapolation():
    # 10 of 20 posts in 100s -> about 100s remaining
    text = line(done=10, total=20, files=1, started=0.0, now=100.0)
    assert "~01:40 left" in text


def test_hours_are_rendered():
    text = line(done=1, total=2, files=1, started=0.0, now=7325.0)
    assert "2:02:05 elapsed" in text
