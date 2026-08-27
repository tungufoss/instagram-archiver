"""Choosing which downloaded .mp4 to keep.

Instagram's player fetches several renditions of the same video, sometimes
with sound as a separate track. Every candidate for one slide describes the
same video, so exactly one file should survive.
"""

from pathlib import Path

from instagram_archiver.media import Candidate, pick_tracks


def cand(name, size, kinds=None, pixels=0):
    return Candidate(path=Path(name), url=f"https://cdn/{name}", size=size,
                     kinds=kinds, pixels=pixels)


def test_no_candidates():
    assert pick_tracks([]) == (None, None)


def test_single_candidate_is_kept():
    only = cand("a.mp4", 1000, {"video", "audio"}, 2_073_600)
    assert pick_tracks([only]) == (only, None)


def test_renditions_of_one_video_collapse_to_the_best():
    """The bug this guards: 37 renditions must not become 37 files."""
    low = cand("low.mp4", 1_000, {"video", "audio"}, 640 * 360)
    mid = cand("mid.mp4", 5_000, {"video", "audio"}, 1280 * 720)
    high = cand("high.mp4", 9_000, {"video", "audio"}, 1920 * 1080)

    video, audio = pick_tracks([low, high, mid])
    assert video is high
    assert audio is None


def test_resolution_beats_file_size():
    big_but_small_frame = cand("a.mp4", 90_000, {"video", "audio"}, 640 * 360)
    small_but_hd = cand("b.mp4", 10_000, {"video", "audio"}, 1920 * 1080)
    video, _ = pick_tracks([big_but_small_frame, small_but_hd])
    assert video is small_but_hd


def test_size_breaks_resolution_ties():
    lower_bitrate = cand("a.mp4", 1_000, {"video"}, 1920 * 1080)
    higher_bitrate = cand("b.mp4", 8_000, {"video"}, 1920 * 1080)
    video, _ = pick_tracks([lower_bitrate, higher_bitrate])
    assert video is higher_bitrate


def test_separate_audio_track_is_paired():
    silent = cand("v.mp4", 9_000, {"video"}, 1920 * 1080)
    sound = cand("a.mp4", 500, {"audio"})
    video, audio = pick_tracks([silent, sound])
    assert video is silent
    assert audio is sound


def test_best_audio_rendition_is_chosen():
    silent = cand("v.mp4", 9_000, {"video"}, 1920 * 1080)
    low_audio = cand("a1.mp4", 300, {"audio"})
    high_audio = cand("a2.mp4", 900, {"audio"})
    _, audio = pick_tracks([silent, low_audio, high_audio])
    assert audio is high_audio


def test_audio_ignored_when_video_already_has_sound():
    complete = cand("v.mp4", 9_000, {"video", "audio"}, 1920 * 1080)
    stray_audio = cand("a.mp4", 500, {"audio"})
    video, audio = pick_tracks([complete, stray_audio])
    assert video is complete
    assert audio is None


def test_without_ffprobe_largest_wins_and_no_mux_attempted():
    a = cand("a.mp4", 1_000)
    b = cand("b.mp4", 7_000)
    video, audio = pick_tracks([a, b])
    assert video is b
    assert audio is None


def test_audio_only_candidates_still_return_something():
    a = cand("a.mp4", 500, {"audio"})
    b = cand("b.mp4", 900, {"audio"})
    video, audio = pick_tracks([a, b])
    assert video is b
    assert audio is None
