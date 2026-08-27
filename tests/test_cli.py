"""CLI argument parsing. Does not launch a browser."""

import pytest

from instagram_archiver.cli import parse_args


def test_defaults():
    args = parse_args(["profile", "https://www.instagram.com/x/"])
    assert args.command == "profile"
    assert args.max_posts is None
    assert args.videos is False          # photographs only, by default
    assert args.headless is False


def test_global_flags_precede_subcommand():
    args = parse_args(
        ["--videos", "--headless", "--out", "shots", "post",
         "https://www.instagram.com/p/ABC/"]
    )
    assert args.videos is True
    assert args.headless is True
    assert str(args.out) == "shots"
    assert args.command == "post"


def test_max_posts_parsed():
    args = parse_args(
        ["profile", "https://www.instagram.com/x/", "--max-posts", "3"]
    )
    assert args.max_posts == 3


def test_login_needs_no_url():
    args = parse_args(["login"])
    assert args.command == "login"
    assert args.url is None


def test_subcommand_required():
    with pytest.raises(SystemExit):
        parse_args([])


# --- flag position must not matter ----------------------------------------

URL = "https://www.instagram.com/someaccount/"


def test_flag_after_subcommand_is_accepted():
    """`profile URL --videos` used to fail with a usage error."""
    assert parse_args(["profile", URL, "--videos"]).videos is True


def test_flag_before_subcommand_survives_the_subcommand_pass():
    assert parse_args(["--videos", "profile", URL]).videos is True


def test_flags_may_be_mixed_either_side():
    args = parse_args(["--videos", "profile", URL, "--nested"])
    assert args.videos is True
    assert args.flatten is False


def test_old_skip_videos_flag_still_parses():
    """It is the default now, but typing it must not be an error."""
    assert parse_args(["--skip-videos", "profile", URL]).videos is False
    assert parse_args(["profile", URL, "--skip-videos"]).videos is False


def test_value_flags_work_after_the_subcommand():
    args = parse_args(["post", "https://www.instagram.com/p/A/", "--out", "shots"])
    assert str(args.out) == "shots"


def test_unsupplied_flags_are_false_not_none():
    args = parse_args(["profile", URL])
    assert args.videos is False
    assert args.include_reels is False
    assert args.flatten is True          # flat is the default layout
    assert args.headless is False
    assert args.out is None


def test_force_defaults_off_and_parses_either_side():
    assert parse_args(["profile", URL]).force is False
    assert parse_args(["--force", "profile", URL]).force is True
    assert parse_args(["profile", URL, "--force"]).force is True


# --- layout ---------------------------------------------------------------


def test_flat_is_the_default_layout():
    assert parse_args(["profile", URL]).flatten is True


def test_nested_opts_out():
    assert parse_args(["--nested", "profile", URL]).flatten is False
    assert parse_args(["profile", URL, "--nested"]).flatten is False


def test_old_flatten_flag_still_parses():
    """It is the default now, but typing it must not be an error."""
    assert parse_args(["--flatten", "profile", URL]).flatten is True


def test_relayout_command_needs_no_url():
    args = parse_args(["relayout"])
    assert args.command == "relayout"
    assert args.flatten is True
    assert args.dry_run is False
