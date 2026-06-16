# Changelog

## 0.2.2 - 2026-06-16

- Publish macOS and Windows desktop zip assets automatically from version tags.
- Includes the packaged YouTube download fixes from 0.2.1 for distributed app builds.

## 0.2.1 - 2026-06-16

- Bundle and configure `certifi` CA certificates for packaged desktop downloads.
- Apply the bundled CA certificate environment to both video and caption downloads.
- Add optional browser-cookie support for YouTube videos that require sign-in.

## 0.2.0 - 2026-06-16

- Rename the public project identity to Slidewright.
- Update the primary CLI command to `slidewright` while keeping `tube2slides` and `youtube-slides` aliases.
- Rename desktop app bundles and GitHub Actions artifacts to Slidewright.

## 0.1.1 - 2026-06-16

- Fix packaged desktop apps so YouTube downloads use the bundled `yt_dlp` Python package when no system `yt-dlp` executable is installed.
- Point `yt-dlp` at the bundled ffmpeg binary during video download and merge.

## 0.1.0 - 2026-06-16

Initial public release.

- Extract distinct slide frames from YouTube URLs or local video files.
- Export slide PNGs, JSON manifests, contact sheets, PowerPoint decks, and HTML reading views.
- Add caption-derived speaker notes from English YouTube captions.
- Add optional AI narrative generation through the OpenAI Responses API with a per-run API key prompt.
- Provide native desktop app builds for macOS and Windows through PyInstaller build scripts and GitHub Actions.
