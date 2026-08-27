# Security Policy

## Supported versions

Only the latest release is supported.

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://github.com/tungufoss/instagram-archiver/security/advisories/new)
rather than opening a public issue. Expect an initial response within a week.

## Scope notes

This tool is deliberately narrow, and some things people report are working as
intended:

- **It cannot see private content you do not have access to.** That is a
  server-side restriction and not a bug.
- **It never reads, stores or transmits your password, cookies or session
  tokens.** The session lives only in a local Playwright profile directory on
  your own machine. If you find code that violates this, that *is* a security
  bug - please report it.
- **Requests to add CAPTCHA solving, anti-bot evasion, credential handling or
  private-content bypass will be declined**, and are out of scope for this
  policy.

## Protecting your own data

`browser_profile/` contains a live logged-in Instagram session. Treat it like a
password: it is gitignored, and you should not copy, share or back it up to a
shared location.
