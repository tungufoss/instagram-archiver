"""Follower names taken from the responses Instagram sends, not the rendered rows.

The dialog is virtualised: it draws a window of rows and discards the rest, so
reading the DOM while scrolling misses names no matter how carefully the
scrolling is done - four different strategies each landed between 432 and 459
of an account's 603.

The requests behind that list carry every name exactly once. Listening to them
is the same lesson the video work taught: read the data the page was given,
rather than inferring it from what happens to be on screen.
"""

from __future__ import annotations

import json
import re

# The follower pages come back from these endpoints.
FOLLOWER_ENDPOINT_RE = re.compile(r"/friendships/\d+/followers|graphql", re.I)


def usernames_in(payload) -> list[str]:
    """Every username in a decoded response, in the order they appear."""
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            name = node.get("username")
            if isinstance(name, str) and name:
                found.append(name)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found


class FollowerFeed:
    """Collects follower names from the responses the dialog triggers."""

    def __init__(self, page):
        self._names: dict[str, None] = {}
        self._responses = 0
        page.on("response", self._on_response)

    def _on_response(self, response) -> None:
        try:
            if not FOLLOWER_ENDPOINT_RE.search(response.url):
                return
            body = response.text()
        except Exception:
            return
        if "username" not in body:
            return
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return

        before = len(self._names)
        for name in usernames_in(payload):
            self._names.setdefault(name, None)
        if len(self._names) > before:
            self._responses += 1

    @property
    def names(self) -> list[str]:
        return list(self._names)

    @property
    def responses(self) -> int:
        return self._responses
