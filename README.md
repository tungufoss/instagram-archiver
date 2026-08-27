# instagram-archiver

[![CI](https://github.com/tungufoss/instagram-archiver/actions/workflows/ci.yml/badge.svg)](https://github.com/tungufoss/instagram-archiver/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Save local copies of the Instagram **photographs** that **your own logged-in
account can already see** at full resolution, with metadata, in a sensible folder structure — a class
group, a family account, your own posts.

Photographs are saved by default. `--videos` adds videos, and `--include-reels`
adds reels; a video that is not saved leaves a labelled placeholder so nothing
goes missing silently.

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

### 4. Or just the videos a photos-only run skipped

```bash
instagram-archiver fill-videos
```

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

Switching layout does not re-download anything. If a file is already in the
archive, changing `--flatten` moves it into its new place and updates the
index; folders left empty are tidied up. It works in both directions, and a
run that only changes layout reports `Files downloaded: 0`.

### Placeholders for videos that were not saved

With `--skip-videos`, a carousel slide that held a video would otherwise leave
a silent gap: the numbering jumps and nothing records that anything was there.
Instead a placeholder image is written in its place:

```text
someaccount/
  2026-08-17_DcJvpIRjwJa/
    01.jpg
    02.video-not-saved.png     <- a video was here
    03.jpg
```

It is a plain grey PNG, so it sorts into the right position in any photo
browser and is obviously not a photograph. The index records it with
`media_type` of `video_skipped`.

### File dates

Each saved file's modified time is set to **when the post was made**, not when
you downloaded it, so the archive sorts chronologically in any file browser.
Instagram strips EXIF from uploads, so the filesystem timestamp is the only
honest place to record this.

### Comments

`--comments` records each post's comments in `comments.csv` and
`comments.json` beside the media — username, time and text, one row each:

| Column | Meaning |
| --- | --- |
| `post_url` | the post they belong to |
| `post_id` | Instagram's shortcode |
| `post_date` | the post's own date |
| `username` | who wrote it |
| `timestamp` | when, ISO 8601 |
| `text` | what they wrote |

**Off by default, deliberately.** Comments are other people's words about
someone's post, so collecting them should be a choice rather than a side
effect of archiving your own photographs. They are kept in their own files
rather than the media index, which describes files on disk.

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

### Picking up where you left off

`--resume` skips posts the index shows are already complete, instead of
visiting each one to discover there is nothing to do. On a finished archive of
39 posts that is 29 seconds rather than 14 minutes. A post counts as complete
when the index holds rows for it and, if you asked for videos, none of them is
still a placeholder.

`fill-videos` goes further when all you want is the videos an earlier run
skipped. It reads the index, visits only the posts holding a placeholder, and
ignores the profile entirely:

```bash
instagram-archiver fill-videos
```

Filling in 15 videos across 6 posts took 131 seconds, against about 14 minutes
to walk the whole profile. `--force` ignores the index and fetches
everything again, which is what you want after changing *what* gets saved.

A file's number is its position in the post, not a running count of what a
particular run downloaded. That way a photo keeps the same name whether or not
videos were saved alongside it.

## Two viewpoints

What this tool can record depends on whose eyes it is looking through.

**As a viewer** — an account you follow, or a public one. This is the case
everything here has been built and tested against.

**As the account itself** — logged in as it, in its own browser profile.
Instagram shows an account things about itself that it shows nobody else.

| | As a viewer | As the account |
| --- | --- | --- |
| Photographs, at full resolution | yes | yes |
| Videos, correctly attributed | yes | yes |
| Captions, dates, exact timestamps | yes | yes |
| Like counts, comment counts | yes | yes |
| Post or reel, photo and video counts | yes | yes |
| Comments themselves | only those the page loads | probably the same |
| View counts | **no** — Instagram returns null | expected, unverified |
| Follower list | **a large sample, not all** | expected, unverified |

The two "expected, unverified" rows are honest guesses, not findings. Nothing
here has been run while logged in as the account it was reading, so whether
Instagram then fills in `view_count` or serves the whole follower list is
untested. To try it, give that account its own browser profile:

```bash
instagram-archiver --browser-profile ./that-account login
instagram-archiver --browser-profile ./that-account followers https://www.instagram.com/thataccount/
```

### Why the follower list is a sample

The dialog is virtualised: it renders a window of rows and discards the rest.
Five strategies — jumping to the bottom, small overlapping steps, a bridge
check, loading fully then walking back, and listening to network responses —
each returned between 432 and 459 of one account's 603.

So a snapshot is recorded with `complete: false` and the count it fell short
of, and **two partial snapshots are not compared**. Comparing them would
invent departures: a name missing from one run is usually a name that run did
not see, not somebody who left. The count trend stays useful; the names are a
large sample of the membership.

When a snapshot does match the stated count, the comparison runs normally and
`joined` / `left` mean what they say.

## How long does it take?

Measured against a public, carousel-heavy account: **166 seconds for 5 posts —
about 33 seconds per post**, producing 45 files and 57 MB.

| Posts | Rough time |
| --- | --- |
| 5 | ~3 minutes |
| 20 | ~10 minutes |
| **45** | **~25 minutes** |
| 100 | ~55 minutes |

Most of that is deliberate waiting, not transfer: 3–6 s between posts, 1–2 s
between carousel slides, and 3 s on each video slide so the browser actually
requests the file. A profile of single photos runs far quicker than one full of
16-slide carousels, so treat these as a middle estimate rather than a promise.

Leave it running. There is no resume flag, but re-running is cheap: everything
already in the index is skipped, so an interrupted run picks up where it left
off.

Video-heavy private accounts are considerably slower than the public account
measured above — roughly 100–200 s per post rather than 33 s, because each
video slide waits for playback to start and then downloads the file. A profile
of mostly photos is much closer to the figures in the table.

Watch progress live with a status line printed after every post:

```text
  [######..................]  26.7%  12/45 posts | 148 files | 09:12 elapsed | ~25:18 left
```

## Options

| Flag | Meaning |
| --- | --- |
| `--out DIR` | where to save media (default `./ig_archiver`) |
| `--browser-profile DIR` | override the session directory |
| `--headless` | no window; only useful after `login` has succeeded once |
| `--videos` | also download videos (off by default) |
| `--include-reels` | also archive reels listed on a profile (off by default) |
| `--comments` | also record comments (off by default) |
| `--resume` | skip posts the index shows are complete |
| `--force` | ignore the index and fetch everything again, overwriting what is there |
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
address. Watching network traffic does not help either: the browser prefetches
videos belonging to *other* posts, so choosing among the `.mp4` requests by
size or arrival order is guesswork. Measured on one post: 8 mp4 requests
covering 3 distinct videos, on a page where nothing was played. That guesswork
once put a stranger's video inside a family carousel.

Instead, Instagram server-renders the post into the page as JSON, including a
`carousel_media` array with a `video_versions` list per slide. The tool reads
that: the page's own answer to which video belongs to slide 4, at the highest
resolution offered. When a slide's video is not named there, the tool writes a
placeholder and says so rather than saving a guess.

### Author and date

Reels render **no `<time>` element at all**, and their page is surrounded by
advertiser links, so reading the author from the DOM picks up a sponsor. The
`og:description` tag carries both facts in a stable shape and is used instead:

```text
628K likes, 4,110 comments - someaccount on April 1, 2026: "caption..."
```

In profile mode the account name comes from the profile URL, which is better
than any guess.

### Reels are ordinary posts

A profile links some of its own posts as `/reel/<code>/` — typically the ones
holding only a video. They are that account's posts and are archived like any
other, in the same folder, in date order. `--skip-reels` leaves them out.

They are read from their `/p/` URL: `/reel/<code>/` renders a scrolling player
full of other people's reels and omits the post's own media from the page.

`--include-reels` turns them back on. Passing a reel URL to `post` mode always
works and is unaffected by this flag.

**Co-authored posts.** Instagram lets two accounts share a post, and it appears
on both their grids. In `profile` mode it is filed under the profile you are
archiving. In `post` mode there is no such context, so it is filed under
whichever author Instagram names first - which may not be the account you had
in mind. See [#9](https://github.com/tungufoss/instagram-archiver/issues/9).

**Known rough edge:** reel pages are the weakest part of the tool. They render
no `<time>` element, their author has to be read from `og:description` because
the surrounding links are advertisements, and they are the slowest pages to
process. If a reel is the only copy of something you need, fetch it directly
with `post` and check the result.

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
- Video quality is whatever Instagram offers, not an original master.
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
