"""CLI argument parsing. Does not launch a browser."""

import pytest

from instagram_archiver.cli import build_parser


def test_defaults():
    args = build_parser().parse_args(["profile", "https://www.instagram.com/x/"])
    assert args.command == "profile"
    assert args.max_posts is None
    assert args.skip_videos is False
    assert args.headless is False


def test_global_flags_precede_subcommand():
    args = build_parser().parse_args(
        ["--skip-videos", "--headless", "--out", "shots", "post",
         "https://www.instagram.com/p/ABC/"]
    )
    assert args.skip_videos is True
    assert args.headless is True
    assert str(args.out) == "shots"
    assert args.command == "post"


def test_max_posts_parsed():
    args = build_parser().parse_args(
        ["profile", "https://www.instagram.com/x/", "--max-posts", "3"]
    )
    assert args.max_posts == 3


def test_login_needs_no_url():
    args = build_parser().parse_args(["login"])
    assert args.command == "login"
    assert args.url is None


def test_subcommand_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
