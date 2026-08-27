# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `scan`, which records what a profile posted without downloading anything:
  date and exact timestamp, post or reel, photo and video counts, likes,
  comment count and caption, one row per post in `posts.csv` / `posts.json`
  in the account's folder. About 3 seconds a post against 30 for archiving.
- `followers`, which records who follows an account and reports who joined or
  left since the last snapshot. Explicitly asked for, never part of a
  normal run.
- Like counts and comment counts on every post.
- Comments read from the rendered page, since Instagram does not put them in
  the page JSON - `preview_comments` is empty even on a post with 4,193.

### Known issues

- **A follower list is complete only when logged in as the account.** Read as
  a viewer the dialog is virtualised and five strategies each returned between
  432 and 459 of one account's 603; logged in as that account the same code
  returned all 606. The shortfall is reported rather than passed off as the
  whole list, and partial snapshots are never compared.
- **Like counts read as a viewer can be placeholders.** The same public
  account reported 3 likes on four older posts to a viewer and 41, 54, 34 and
  28 to itself. Recent posts agreed. Treat a viewer's like count as a lower
  bound.
- **Comment capture is thin.** Only what the page has loaded is read, which is
  a handful on a busy post.
- **View counts are not available to anyone**, including the account itself.
  Instagram leaves `view_count` null in the served page. Recorded as blank
  rather than zero, since a null is not a zero.

## [0.2.0] - 2026-08-27

Videos work. Reels are archived. Captions and comments are recorded.

### Added

- **Videos**, downloaded correctly and on by default with `--videos`.
- `--comments` records each post's comments - username, time and text - in
  `comments.csv` and `comments.json`. Off by default: comments are other
  people's words about someone's post, so collecting them should be a choice.
- Post captions in the index, so an archive says what each post was about
  rather than only what it contained.
- `fill-videos`, which reads the index and visits only the posts holding a
  placeholder: 15 videos across 6 posts in 131 seconds, against about 14
  minutes for a full pass.
- `--resume`, which skips posts the index records as complete. A finished
  45-post archive re-runs in 29 seconds instead of 14 minutes.
- `relayout`, to rearrange an archive already on disk. No browser, no network:
  354 files in 3.7 seconds.
- `--force`, to ignore the index and fetch everything again.
- Placeholder images for videos that were not saved, so a skipped video leaves
  a visible marker in the right position instead of a silent gap.
- A run log written automatically beside the media.
- A progress line after each post, with counts, elapsed time and an estimate.

### Changed

- A flat account folder is the default layout; `--nested` gives each post its
  own folder.
- Posts the profile links as reels are archived by default, beside the
  account's other posts. They had been skipped on the mistaken understanding
  that a reel duplicates a video already in a post; in fact they are ordinary
  posts, usually the ones holding only a video, and skipping them lost six of
  one account's forty-five posts outright. `--skip-reels` leaves them out.
- A file already on disk has its index row rewritten rather than skipped, so
  details learned since it was saved reach the index without refetching it.

### Fixed

- **Videos were attributed by watching network traffic**, which cannot tell one
  post's video from another post's prefetch: a page holding one video issued 8
  requests covering 3 distinct videos, and the guess put a stranger's video
  inside a family carousel. Instagram server-renders the post into the page as
  JSON with a `video_versions` list per slide, so which video belongs to which
  slide is now read rather than inferred. Verified on a 12-slide post: videos
  at slides 4, 6 and 8, durations matching the page to the millisecond. It is
  also much faster, since nothing waits for playback or downloads renditions to
  discard them. Closes #8.
- **Re-running destroyed data.** A file was fetched onto its destination,
  overwriting a photograph already there, then deleted when its hash turned out
  to be known. A verified 12-item folder came back holding 3 placeholders. The
  destination is not a scratch area: a file already in place is left alone.
- **Three carousel slides are mounted at once** - previous, current and next -
  and all three were read, so a video mounted as the *next* slide was recorded
  at the current position. A 12-slide post produced 16 files with placeholders
  on slides holding photographs. Only the slide actually on screen is read now.
- **Instagram no longer wraps a standalone post in `<article>`**, so every
  selector scoped to it silently found nothing. Selectors fall back to `<main>`,
  with suggested posts excluded by the fact that their thumbnails sit inside an
  `<a href="/p/...">` link - size alone was not enough, those thumbnails can
  exceed 300 px.
- A reel is read from its `/p/` URL. `/reel/<code>/` renders a scrolling player
  full of other people's reels and omits the post's own media, so archiving one
  could save whatever the player had centred.
- Reels render no `<time>` element and are surrounded by advertiser links, so
  author and date are read from `og:description`, which was previously
  producing an advertiser's name and `unknown-date`.
- File numbering counted files actually written rather than the slide's
  position in the post, so anything skipped shifted every later number.
- The index was written only at the end of a run, so an interrupt lost the
  record of everything already fetched.
- Flags such as `--videos` were rejected when written after the subcommand.
- Output is line-buffered, so a piped log shows progress as it happens.
- Folders that could not be removed after a layout change failed silently. On
  Windows this is usually OneDrive holding them; it is now reported.
- Console output no longer crashes on emoji under Windows' cp1252 default.

### Known issues

- A post co-authored by two accounts is filed under whichever author Instagram
  names first when archived through `post` mode. `profile` mode files it under
  the profile being archived. See
  [#9](https://github.com/tungufoss/instagram-archiver/issues/9).

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

[Unreleased]: https://github.com/tungufoss/instagram-archiver/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tungufoss/instagram-archiver/releases/tag/v0.2.0
[0.1.0]: https://github.com/tungufoss/instagram-archiver/releases/tag/v0.1.0
