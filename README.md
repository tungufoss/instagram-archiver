# instagram-archiver

[![CI](https://github.com/tungufoss/instagram-archiver/actions/workflows/ci.yml/badge.svg)](https://github.com/tungufoss/instagram-archiver/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Save local copies of Instagram photos and videos that **your own logged-in
account can already see** — a class group, a family account, your own posts —
at full resolution, with metadata, in a sensible folder structure.

It drives a real Chromium window through Playwright using a persistent local
browser profile. You log in by hand once; the session is reused after that.

## What it deliberately does not do

- **No credentials in code or config.** Your password, cookies and session
  tokens are never read, stored or transmitted by this tool. The session lives
  only in a local browser profile directory on your machine.
- **No bypassing anything.** Private-account rules, blocks and pending follow
  requests all still apply. If your account cannot see a post, neither can this.
- **No CAPTCHA solving, no anti-bot evasion, no fingerprint spoofing.**
- **No hammering.** Requests are paced: 1–2 s between carousel slides, 3–6 s
  between posts.

If you need something outside those lines, this is the wrong tool.

## Install

```bash
pip install git+https://github.com/tungufoss/instagram-archiver.git
python -m playwright install chromium
```

Or from a clone, for development:

```bash
git clone https://github.com/tungufoss/instagram-archiver.git
cd instagram-archiver
pip install -e ".[dev]"
python -m playwright install chromium
```

### ffmpeg (optional, recommended)

Instagram sometimes delivers one video as two files — picture in one, sound in
the other. With `ffmpeg` and `ffprobe` on your PATH, the tool detects this and
merges them losslessly. Without them it keeps only the larger file, so such a
video may end up silent. This is common for reels, so it is worth installing.

| Platform | Command |
| --- | --- |
| Windows | `winget install Gyan.FFmpeg` |
| macOS | `brew install ffmpeg` |
| Debian/Ubuntu | `sudo apt install ffmpeg` |

## Usage

### 1. Log in, once, by hand

```bash
instagram-archiver login
```

A visible Chromium window opens on the Instagram login page. Log in yourself,
including any two-factor step. The tool only polls until a session exists, then
exits. Nothing is typed for you.

**The session is stored in a fixed per-user location**, not next to your files,
so every later run reuses it no matter which directory you run from:

| Platform | Session directory |
| --- | --- |
| Windows | `%LOCALAPPDATA%\instagram-archiver\browser_profile` |
| macOS | `~/Library/Application Support/instagram-archiver/browser_profile` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/instagram-archiver/browser_profile` |

To log in as a different account, delete that directory and run `login` again.
Override it with `--browser-profile DIR` if you want to keep several accounts
side by side.

### 2. Archive a profile

```bash
instagram-archiver profile https://www.instagram.com/someaccount/
```

Start small to check the output looks right:

```bash
instagram-archiver profile https://www.instagram.com/someaccount/ --max-posts 3
```

### 3. Or a single post

```bash
instagram-archiver post https://www.instagram.com/p/ABC123/
```

Works with `/p/` and `/reel/` URLs.

## Output

Files land in `./ig_archiver/` in whatever directory you run from, one
subfolder per account. Move them wherever you like afterwards, or point
somewhere else with `--out`.

```text
ig_archiver/
  index.csv
  index.json
  someaccount/
    2026-08-17_DcJvpIRjwJa/
      01.jpg
      02.jpg
      03.mp4
    2026-07-08_DZsluBdCreP/
      01.jpg
```

With `--flatten`, the per-post folders go away and the names carry the same
information:

```text
ig_archiver/
  someaccount/
    2026-08-17_DcJvpIRjwJa_01.jpg
    2026-08-17_DcJvpIRjwJa_02.jpg
    2026-07-08_DZsluBdCreP_01.jpg
```

Photos and videos share one numbering sequence per post, in carousel order.

### File dates

Each saved file's modified time is set to **when the post was made**, not when
you downloaded it, so the archive sorts chronologically in any file browser.
Instagram strips EXIF from uploads, so the filesystem timestamp is the only
honest place to record this.

### The index

`index.csv` and `index.json` sit at the root of the output directory and are
**merged, never overwritten**. Each run loads the existing index, skips
anything already recorded, appends the new rows and rewrites both files.

| Column | Meaning |
| --- | --- |
| `post_url` | canonical post URL |
| `username` | account that posted it |
| `post_id` | Instagram's shortcode |
| `post_date` | the post's own date |
| `media_type` | `image` or `video` |
| `carousel_index` | position within the post |
| `filename` | file on disk |
| `relative_path` | path relative to the output directory |
| `source_url` | CDN URL it came from |
| `sha256` | hash of the bytes |

Re-running is safe: hashes are loaded from the index first, so files already on
disk are never downloaded twice.

## Options

| Flag | Meaning |
| --- | --- |
| `--out DIR` | where to save media (default `./ig_archiver`) |
| `--browser-profile DIR` | override the session directory |
| `--headless` | no window; only useful after `login` has succeeded once |
| `--skip-videos` | photographs only |
| `--flatten` | no per-post folders; date and post ID go in the filename |
| `--max-posts N` | (profile mode) stop after N posts |
| `--version` | print the version |

## How it works

### Finding the post's own media

Instagram does not reliably wrap a standalone post in `<article>` any more, so
the tool falls back to `<main>`. That puts the "more posts" grid in scope, and
the discriminator that actually works is this: **a suggested post's thumbnail
is always inside an `<a href="/p/...">` link, and the post's own media never
is.** Size alone is not enough — suggestion thumbnails can exceed 300 px.

Also skipped: anything inside `<header>`, anything with `alt` containing
"profile picture", anything under 200 px on screen, any image whose slide also
contains a `<video>` (that's a poster frame), and any response under 5 KB.

Photos are taken at the widest candidate in each `<img>`'s `srcset`, which is
the highest resolution Instagram served your browser — typically 2500–3900 px
wide, far above the 640 px `og:image` preview.

### Videos

A `<video>` element's `src` is a `blob:` URL, so the DOM holds no downloadable
address. Instead the tool watches the page's own network requests and keeps any
`.mp4` fetched from an Instagram or Facebook CDN host. On each slide it starts
the video muted so the browser actually requests the file, waits three seconds,
then collects what was requested. Players fetch byte ranges, so `bytestart` and
`byteend` are stripped before downloading, which makes the CDN return the whole
file.

### Author and date

Reels render **no `<time>` element at all**, and their page is surrounded by
advertiser links, so reading the author from the DOM picks up a sponsor. The
`og:description` tag carries both facts in a stable shape and is used instead:

```text
628K likes, 4,110 comments - someaccount on April 1, 2026: "caption..."
```

In profile mode the account name comes from the profile URL, which is better
than any guess.

### Carousels and deduplication

Carousels are walked by clicking Next until it disappears (capped at 25 slides),
harvesting after each step. Files are deduplicated twice: by the stable part of
the CDN filename within a post, and by SHA-256 across the whole library.

## Troubleshooting

**"This profile is private and the account you are logged in as does not follow it"**
Exactly what it says. Follow the account and wait to be accepted, or log in as
an account that already follows it. There is no workaround, by design.

**Zero posts found on a public profile**
Likely an Instagram markup change. Open the profile in the same Chromium window
yourself to confirm what you can see, then file a bug.

**A video has no sound**
Install ffmpeg (see above) and re-run.

**A carousel slide's video was missed**
Raise `VIDEO_SETTLE` in `src/instagram_archiver/config.py`.

## Limits

- Video quality is whatever Instagram serves your browser — typically a
  compressed rendition, not an original master.
- Stories, highlights and archived posts are not covered.
- Instagram changes its markup without warning; selectors may need updating.

## Your data

The session directory holds a live logged-in session. **Treat it like a
password** — do not copy or share it. Downloaded media is gitignored.

Please respect the people in the photos you save. Content that other people
shared privately with you was shared with *you* — archiving it for yourself is
not permission to republish it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), particularly the scope section.
Security issues: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
