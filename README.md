# Tube2Slides

Turn YouTube lectures and technical talk videos into readable slide decks.

Tube2Slides extracts distinct presentation slides from a YouTube URL or local video, exports numbered PNG slides, and can build a PowerPoint deck plus an HTML reading view. The native desktop app is intended for coworkers who want a simple no-server workflow on macOS or Windows.

## Features

- Extract unique slide frames from YouTube lectures or local videos.
- Export slide PNGs, a JSON manifest, and a contact sheet.
- Create editable PowerPoint decks.
- Create an HTML reading view for quick review.
- Add caption-derived speaker notes with no OpenAI token usage.
- Optionally generate AI narrative notes from captions using the OpenAI Responses API.
- Build native macOS and Windows desktop apps with PyInstaller.

## Best Way To Use It

For nontechnical users, use the native desktop app from the GitHub release. No shared server is required. The app runs locally, bundles the video tooling it needs, and saves each lecture into a local job folder.

1. Open **YouTube Lecture Slides**.
2. Paste a YouTube lecture URL or choose a local video.
3. Choose an output folder.
4. Pick a narrative mode.
5. Click **Extract**.

See [docs/NATIVE_APP.md](docs/NATIVE_APP.md) for distribution and build details.

## Narrative Modes

- **No notes**: extracts slides only.
- **Caption notes**: downloads English YouTube captions and places the matching caption segment into PowerPoint speaker notes. This does not use OpenAI tokens.
- **AI narrative**: asks for an OpenAI API key for that run only, sends caption excerpts to the OpenAI Responses API, and writes concise reader-friendly speaker notes. The key is not saved by the app.

## CLI Install

From this directory:

```bash
python3 -m pip install -e .
```

For YouTube URL support in CLI mode, install the downloader extra:

```bash
python3 -m pip install -e ".[download]"
```

The legacy command name `youtube-slides` is still available, but `tube2slides` is the preferred command.

## CLI Usage

Extract slides from a local file:

```bash
tube2slides talk.mp4 -o slides
```

Extract slides from YouTube:

```bash
tube2slides "https://www.youtube.com/watch?v=VIDEO_ID" -o slides
```

Useful options:

```bash
tube2slides talk.mp4 \
  --sample-interval 2 \
  --min-stable-samples 2 \
  --similarity-threshold 20 \
  --crop 120,80,1680,945 \
  -o slides
```

The output directory contains:

- `slide_001.png`, `slide_002.png`, ...
- `manifest.json` with timestamps and scoring metadata
- `index.html` contact sheet

## Build Desktop Apps

Build the macOS app on macOS:

```bash
./scripts/build_macos.sh
```

Build the Windows app on Windows:

```powershell
.\scripts\build_windows.ps1
```

GitHub Actions can also build both platforms from the **Build desktop apps** workflow.

## Requirements

- Python 3.10+
- `ffmpeg` on your `PATH` for CLI use
- `yt-dlp` for YouTube URL support in CLI use

The packaged desktop app includes Python dependencies, `yt-dlp`, and a bundled `ffmpeg` binary via `imageio-ffmpeg`.

## Notes

The extractor samples frames with `ffmpeg`, scores slide-like frames, de-duplicates near-identical frames with perceptual hashes, and writes high-quality PNG output. If a talk uses picture-in-picture or a fixed room camera, pass `--crop x,y,w,h` in CLI mode to isolate the slide area before hashing and export.

For fast-moving animations, lower `--sample-interval`. For noisy scene changes, raise `--min-stable-samples`.

## License

Apache-2.0. See [LICENSE](LICENSE).
