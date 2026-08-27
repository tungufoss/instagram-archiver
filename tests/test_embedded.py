"""Reading the post's own media list out of the page's embedded JSON.

This replaced watching network traffic, which could not tell one post's video
from another's prefetch and put a stranger's video in a family album.
"""

import json

from instagram_archiver.embedded import parse_blocks, video_urls_by_position

CODE = "ABC123"


def block(payload):
    return json.dumps(payload)


def carousel(kinds):
    """kinds like ['image', 'video', 'image'] -> a carousel_media payload."""
    items = []
    for i, kind in enumerate(kinds, start=1):
        if kind == "video":
            items.append({
                "video_versions": [
                    {"url": f"https://cdn/low{i}.mp4", "width": 480, "height": 360},
                    {"url": f"https://cdn/best{i}.mp4", "width": 960, "height": 720},
                ],
                "image_versions2": {"candidates": [{"width": 960, "height": 720}]},
            })
        else:
            items.append({"image_versions2": {"candidates": [{"width": 1440,
                                                              "height": 1080}]}})
    return {"code": CODE, "carousel_media": items}


def test_reads_a_mixed_carousel():
    media = parse_blocks([block(carousel(["image", "image", "image", "video"]))], CODE)
    assert [m["kind"] for m in media] == ["image", "image", "image", "video"]


def test_picks_the_highest_resolution_rendition():
    media = parse_blocks([block(carousel(["video"]))], CODE)
    assert media[0]["url"] == "https://cdn/best1.mp4"
    assert (media[0]["width"], media[0]["height"]) == (960, 720)


def test_video_positions_are_one_based():
    """The real case: a 12-slide post with videos at 4, 6 and 8."""
    kinds = ["image"] * 12
    for slot in (4, 6, 8):
        kinds[slot - 1] = "video"
    positions = video_urls_by_position(parse_blocks([block(carousel(kinds))], CODE))
    assert sorted(positions) == [4, 6, 8]


def test_single_media_post_is_treated_as_one_item():
    single = {"code": CODE, "video_versions": [
        {"url": "https://cdn/only.mp4", "width": 720, "height": 1280}]}
    media = parse_blocks([block(single)], CODE)
    assert media == [{"kind": "video", "url": "https://cdn/only.mp4",
                      "width": 720, "height": 1280}]


def test_another_posts_json_is_ignored():
    other = {"code": "SOMETHINGELSE", "carousel_media": [
        {"video_versions": [{"url": "https://cdn/not-ours.mp4",
                             "width": 960, "height": 720}]}]}
    assert parse_blocks([block(other)], CODE) is None


def test_blocks_without_our_post_return_none():
    assert parse_blocks([block({"unrelated": True}), "not json at all"], CODE) is None


def test_empty_input():
    assert parse_blocks([], CODE) is None
    assert video_urls_by_position(None) == {}


def test_a_bare_code_reference_is_not_mistaken_for_media():
    """A mention of the post without media detail must not win."""
    stub = {"code": CODE, "like_count": 12}
    real = carousel(["video"])
    media = parse_blocks([block(stub), block(real)], CODE)
    assert media == [{"kind": "video", "url": "https://cdn/best1.mp4",
                      "width": 960, "height": 720}]


def test_malformed_video_versions_fall_back_to_image():
    payload = {"code": CODE, "carousel_media": [{"video_versions": [{"url": None}]}]}
    assert parse_blocks([block(payload)], CODE) == [{"kind": "image"}]
