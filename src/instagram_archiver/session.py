"""Browser session handling.

The whole point of this module: you log in by hand, once, in a real window.
No password, cookie or token is ever read, stored or transmitted by this
package. Playwright keeps the session in a local user-data directory that
belongs to you.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from .config import BROWSER_LOCALE, BROWSER_VIEWPORT, LOGIN_WAIT_MINUTES

LOGIN_URL = "https://www.instagram.com/accounts/login/"

# Set for any signed-in session. We only check that it exists.
SESSION_COOKIE = "ds_user_id"


class NotLoggedIn(RuntimeError):
    """Raised when a session could not be established in time."""


@contextmanager
def browser_session(profile_dir: Path, headless: bool = False):
    """Yield (context, page) backed by a persistent local browser profile."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport=BROWSER_VIEWPORT,
            locale=BROWSER_LOCALE,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            yield context, page
        finally:
            context.close()


def is_logged_in(context) -> bool:
    try:
        return any(c["name"] == SESSION_COOKIE for c in context.cookies())
    except Exception:
        return False


def ensure_login(context, page, wait_minutes: int = LOGIN_WAIT_MINUTES) -> None:
    """Return once a session exists, waiting for the user to log in by hand."""
    if is_logged_in(context):
        print("[ok] existing Instagram session found in the local browser profile.")
        return

    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    print()
    print("=" * 70)
    print(" Please log into Instagram in the Chromium window that just opened.")
    print(" Complete any two-factor prompt yourself. Nothing is typed for you")
    print(" and no password or token is read by this tool.")
    print(f" Waiting up to {wait_minutes} minutes...")
    print("=" * 70)
    print()

    deadline = time.time() + wait_minutes * 60
    while time.time() < deadline:
        if is_logged_in(context):
            print("[ok] logged in. The session is saved in the local browser profile;")
            print("     future runs will reuse it.")
            time.sleep(2)
            return
        time.sleep(2)

    raise NotLoggedIn("Timed out waiting for manual login.")
