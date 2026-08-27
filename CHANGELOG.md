# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Changing the output layout now moves files already in the archive instead of
  downloading them again, in either direction, and tidies up the folders it
  empties. A layout-only run reports `Files downloaded: 0`.

### Fixed

- The run summary counted relocated files as downloads.
- The log line for a placeholder repeated the account folder in its path.
- Single-post runs did not tidy up folders a layout change had emptied.

## [0.1.0] - 2026-08-27

First release. **Photographs only** — see Known limitations.

### Added

- Manual, one-time login in a visible browser window; the session is kept in a
  per-user directory and reused. No password, cookie or token is ever read,
  stored or transmitted by this tool.
- `profile` mode archives every post visible to your session; `post` mode
  archives one post or reel URL.
- Carousels are walked slide by slide, reading only the slide on screen.
- Photographs are saved at the highest resolution the browser was served,
  typically 2500-3900 px wide rather than the 640 px preview.
- Files are stamped with the post's own date, so the archive sorts
  chronologically in any file browser.
- `index.csv` / `index.json` record post URL, username, post ID, date, media
  type, carousel position, filename and SHA-256. Merged, never overwritten.
- Deduplication by CDN filename within a post and by SHA-256 across the whole
  archive, so re-running only fetches what is missing.
- A placeholder image for every video that was not saved, keeping the post's
  real shape instead of a silent gap in the numbering.
- Progress line after each post, with counts, elapsed time and an estimate.
- A run log written automatically beside the media.
- `--force`, `--flatten`, `--include-reels`, `--videos`, `--max-posts`,
  `--out`, `--browser-profile`, `--headless`, `--log`.
- Clear failure when a profile is private and your account does not follow it.

### Verified against

39 posts of a real private account: 331 photographs and 23 placeholders, every
index row backed by a file on disk, every post's numbering matching what
Instagram shows. 15 minutes.

### Known limitations

- **Videos are experimental** and off by default. Instagram prefetches
  unrelated videos on every page, and the tool cannot yet tell which file
  belongs to which slide, so `--videos` can save the wrong one. Photographs
  are unaffected. See
  [#8](https://github.com/tungufoss/instagram-archiver/issues/8).
- **Reels are skipped** in profile mode, for the same reason; they carry no
  photographs, so a photographs-only archive loses nothing. The URLs skipped
  are written to `skipped-reels.txt`.
- Stories, highlights and archived posts are not covered.

[Unreleased]: https://github.com/tungufoss/instagram-archiver/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tungufoss/instagram-archiver/releases/tag/v0.1.0
