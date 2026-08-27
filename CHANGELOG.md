# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `fill-videos`, which reads the index and visits only the posts holding a
  placeholder. Filling 15 videos across 6 posts took 131 seconds against about
  14 minutes to walk the whole profile.
- `--resume`, which skips posts the index shows are already complete rather
  than visiting each one to find out. A finished 39-post archive re-runs in 29
  seconds instead of 14 minutes.

### Fixed

- A reel is now read from its `/p/` URL. Instagram serves `/reel/<code>/` as a
  scrolling reels player showing other people's content and omits the post's
  media from the page, so archiving a reel could save whatever the player had
  centred. The same code at `/p/<code>/` carries the real media list.

### Known issues

- A post co-authored by two accounts is filed under whichever author Instagram
  names first when archived through `post` mode. `profile` mode files it under
  the profile being archived. See
  [#9](https://github.com/tungufoss/instagram-archiver/issues/9).

### Fixed

- **Videos are attributed correctly.** They were chosen by watching network
  traffic, which cannot tell one post's video from another post's prefetch: a
  page with one video issued 8 requests covering 3 distinct videos, and the
  guess put a stranger's video inside a family carousel. Instagram
  server-renders the post into the page as JSON with a `video_versions` list
  per carousel slide, so the tool now reads which video belongs to which slide
  instead of inferring it. Verified on a 12-slide post: the three videos come
  back at slides 4, 6 and 8 with durations matching the page exactly
  (3.30s, 4.03s, 4.63s). Closes #8.
- Video slides no longer wait for playback or download several renditions to
  discard most of them, so a video-heavy post takes about 37 seconds where it
  previously took over three minutes.
- Folders that could not be removed after a layout change failed silently,
  leaving empty directories with nothing to explain them. On Windows this is
  usually OneDrive holding the folder; it is now reported.

### Added

- `relayout`, to rearrange an archive already on disk. No browser, no network:
  354 files took 3.7 seconds.
- A flat account folder is now the default layout; `--nested` gives each post
  its own folder.

### Changed

- `--videos` is no longer marked experimental.

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
