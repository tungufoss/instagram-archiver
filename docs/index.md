# instagram-archiver

Save local copies of Instagram photos and videos that **your own logged-in
account can already see** — a class group, a family account, your own posts —
at full resolution, with metadata, in a sensible folder structure.

[View on GitHub](https://github.com/tungufoss/instagram-archiver){: .btn }

---

## What it does

- Saves **photos at full resolution** — typically 2500–3900 px wide, not the
  640 px preview.
- Saves **videos**, including reels and videos inside carousels.
- Walks **every slide of a carousel**.
- Stamps each file with **the post's own date**, so your archive sorts
  chronologically.
- Keeps a **CSV/JSON index** of everything, and never downloads the same file
  twice.

## What it deliberately does not do

- **No credentials in code or config.** Your password, cookies and session
  tokens are never read, stored or transmitted. You log in by hand in a real
  browser window.
- **No bypassing anything.** Private-account rules, blocks and pending follow
  requests all still apply.
- **No CAPTCHA solving, no anti-bot evasion.**
- **No hammering.** Requests are paced deliberately.

If you need something outside those lines, this is the wrong tool.

---

## Install

```bash
pip install git+https://github.com/tungufoss/instagram-archiver.git
python -m playwright install chromium
```

**Optional but recommended:** install `ffmpeg`. Instagram sometimes delivers a
video's picture and sound as two separate files; with ffmpeg present they are
merged losslessly, and without it such a video may end up silent.

| Platform | Command |
| --- | --- |
| Windows | `winget install Gyan.FFmpeg` |
| macOS | `brew install ffmpeg` |
| Debian/Ubuntu | `sudo apt install ffmpeg` |

---

## Three commands

### 1. Log in, once

```bash
instagram-archiver login
```

A Chromium window opens on the Instagram login page. Log in yourself, including
any two-factor step. Nothing is typed for you. The session is saved to a fixed
per-user directory and reused by every later run.

### 2. Archive a whole profile

```bash
instagram-archiver profile https://www.instagram.com/someaccount/
```

Try a few posts first:

```bash
instagram-archiver profile https://www.instagram.com/someaccount/ --max-posts 3
```

### 3. Archive one post

```bash
instagram-archiver post https://www.instagram.com/p/ABC123/
```

Works with `/p/` and `/reel/` URLs.

---

## What you get

Files land in `./ig_archiver/` in whatever directory you run from, one folder
per account:

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

Prefer everything in one folder? Use `--flatten`:

```text
ig_archiver/
  someaccount/
    2026-08-17_DcJvpIRjwJa_01.jpg
    2026-08-17_DcJvpIRjwJa_02.jpg
```

The index records post URL, username, post ID, date, media type, carousel
position, filename and SHA-256 for every file. It is **merged on each run**,
never overwritten, which is what makes re-runs skip what you already have.

---

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

---

## Options

| Flag | Meaning |
| --- | --- |
| `--out DIR` | where to save media (default `./ig_archiver`) |
| `--browser-profile DIR` | override the session directory |
| `--headless` | no window; only after `login` has succeeded once |
| `--skip-videos` | photographs only |
| `--flatten` | no per-post folders; date and ID go in the filename |
| `--max-posts N` | profile mode: stop after N posts |

---

## Common questions

### It says the profile is private and I do not follow it

That is a server-side restriction, not a bug. Follow the account and wait to be
accepted, or log in as an account that already follows it. There is no
workaround, by design.

### How do I switch Instagram accounts?

Delete the session directory and run `login` again:

| Platform | Session directory |
| --- | --- |
| Windows | `%LOCALAPPDATA%\instagram-archiver\browser_profile` |
| macOS | `~/Library/Application Support/instagram-archiver/browser_profile` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/instagram-archiver/browser_profile` |

### A video came out silent

Install ffmpeg and run it again.

### Zero posts on a public profile

Instagram probably changed its markup. Open the profile in the same Chromium
window to confirm what you can see, then
[file a bug](https://github.com/tungufoss/instagram-archiver/issues/new?template=bug_report.md).

---

## Please be decent about it

Content other people shared privately with you was shared with *you*.
Archiving it for yourself is not permission to republish it, and the people in
those photos did not agree to anything beyond the audience the poster chose.

---

## Links

- [Source and README](https://github.com/tungufoss/instagram-archiver)
- [Report a bug](https://github.com/tungufoss/instagram-archiver/issues)
- [Contributing and scope](https://github.com/tungufoss/instagram-archiver/blob/main/CONTRIBUTING.md)
- [MIT licence](https://github.com/tungufoss/instagram-archiver/blob/main/LICENSE)
