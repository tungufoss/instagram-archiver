# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-27

### Added

- Manual, one-time login in a visible browser window, with the session kept in
  a persistent local Playwright profile.
- `profile` mode: enumerate and archive every post visible to your session.
- `post` mode: archive a single post or reel URL.
- Carousel walking, collecting every unique slide.
- Photographs saved at the highest resolution offered to the browser.
- Video downloading via CDN request sniffing, with optional ffmpeg muxing when
  Instagram splits picture and sound into separate files.
- Deduplication by CDN filename within a post and by SHA-256 across the library.
- `index.csv` / `index.json` recording post URL, post ID, date, media type,
  carousel position, filename and hash.
- Clear failure when a profile is private and your account does not follow it.
- `--flatten` to skip per-post folders and put date and post ID in filenames.
- Saved files are stamped with the post's own date, not the download time.
- Output defaults to `./ig_archiver`, one subfolder per account; the browser
  session lives in a fixed per-user application data directory instead.
- Documentation site under `docs/` for GitHub Pages.

### Fixed

- Instagram no longer wraps a standalone post in `<article>`. Everything scoped
  to that selector silently found nothing; selectors now fall back to `<main>`.
- Suggested posts are excluded by the fact that their thumbnails sit inside an
  `<a href="/p/...">` link. Size filtering alone was not enough, since those
  thumbnails can exceed 300 px.
- Reels render no `<time>` element and surround the media with advertiser
  links, so author and date are now read from `og:description`, which was
  previously producing an advertiser's name and `unknown-date`.
- Console output no longer crashes on emoji under Windows' cp1252 default.
- A video slide saved every rendition Instagram's player fetched, not just one:
  a single reel produced 37 files. All candidates for one slide describe the
  same video, so the best rendition is chosen and any separate audio track is
  merged into it. Picking by resolution rather than file size also gets a
  better copy - the reel that prompted this went from 15 MB at a lower
  resolution to 27 MB at 1440x2560, with sound.

[Unreleased]: https://github.com/tungufoss/instagram-archiver/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tungufoss/instagram-archiver/releases/tag/v0.1.0
