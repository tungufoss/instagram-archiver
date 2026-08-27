# Contributing

Thanks for taking an interest. This is a small, deliberately narrow tool, so
the most useful thing you can do before writing code is open an issue and
check the change fits the scope below.

## Scope: what this project will and will not do

**In scope**

- Saving photos and videos your own logged-in account can already see
- Keeping up with Instagram markup changes when selectors break
- Better metadata, indexing, resumability and output structure
- Packaging, docs, tests and cross-platform fixes

**Out of scope, and pull requests doing these will be closed**

- Bypassing private-account restrictions or accessing anything your account
  cannot see
- CAPTCHA solving, anti-bot evasion, browser fingerprint spoofing
- Reading, storing or transmitting passwords, cookies or session tokens
- Scraping at aggressive rates, or making the pacing defaults faster
- Mass collection across many accounts

This is not negotiable, and it is the reason the tool works the way it does:
a real browser, a manual login, and conservative pacing.

## Development setup

```bash
git clone https://github.com/tungufoss/instagram-archiver.git
cd instagram-archiver
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m playwright install chromium
```

## Running checks

```bash
pytest
ruff check .
```

The test suite is intentionally browser-free: it covers URL handling, index
merging and CLI parsing. Anything that talks to Instagram is verified by hand,
because CI must not log into anyone's account.

## Testing a change by hand

Use a **public** account for smoke tests, and a small `--max-posts` value:

```bash
instagram-archiver profile https://www.instagram.com/someaccount/ --max-posts 2
```

Please do not paste real post URLs, usernames, session data or downloaded
media into issues or pull requests.

## Pull requests

- One focused change per pull request
- Add or update tests for anything with logic in it
- Update `CHANGELOG.md` under `## [Unreleased]`
- Run `pytest` and `ruff check .` before pushing
- Describe how you verified the change against the live site, if relevant

## Reporting selector breakage

Instagram changes its markup without warning. If the tool suddenly finds zero
posts or zero images, that is the likely cause. Useful bug reports include:

- What mode you ran and what it printed
- Whether the account is public or private
- Whether you can see the content yourself in the same browser profile

Never include screenshots containing other people's private content.
