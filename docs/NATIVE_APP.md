# Slidewright Native Desktop App

The desktop app is the easiest no-server option for coworkers. It runs locally, opens a native window, and saves each lecture as a job folder containing slide PNGs, a PowerPoint deck, and an optional HTML reading view.

## User Experience

1. Open **Slidewright**.
2. Paste a YouTube lecture URL.
3. Choose an output folder.
4. If YouTube requires sign-in, choose the browser where you are already signed in.
5. Choose a narrative mode.
6. Click **Extract**.
7. Open the saved `.pptx` or `reading_view.html`.

No shared server is required. The packaged app includes Python dependencies, `yt-dlp`, CA certificates through `certifi`, and a bundled `ffmpeg` binary via `imageio-ffmpeg`.

## Narrative Modes

- **No notes** extracts slides only and does not use captions or API tokens.
- **Caption notes** downloads English YouTube captions and places the matching caption segment into speaker notes. This does not use OpenAI tokens.
- **AI narrative** asks for an OpenAI API key for that run only, sends the caption excerpts to the OpenAI Responses API, and writes concise reader-friendly notes for each slide. The key is not saved by the app.

The AI model field defaults to `gpt-5.5` and is editable for teams that use a different enabled model. When OpenAI returns usage data, the app logs input, output, and total tokens in the progress panel.

If the video has no English captions, the app still produces the slides and deck. AI narrative generation depends on captions, so it cannot summarize a captionless lecture yet.

## Build On Mac

Run on macOS:

```bash
./scripts/build_macos.sh
```

The app is written to:

```text
dist/Slidewright.app
```

For distribution outside your machine, sign/notarize the app with your Apple Developer certificate before sharing broadly.

## Build On Windows

Run in PowerShell on Windows:

```powershell
.\scripts\build_windows.ps1
```

The app is written to:

```text
dist\Slidewright\Slidewright.exe
```

Zip the whole `dist\Slidewright` folder for coworkers. For broad sharing, sign the executable to reduce SmartScreen warnings.

## Why Build On Each OS?

PyInstaller is not a reliable cross-compiler. Build the Mac app on macOS and the Windows app on Windows. A GitHub Actions workflow can automate both builds if the project is pushed to GitHub.

## Limitations

- YouTube access depends on `yt-dlp` and YouTube availability.
- Some YouTube videos require browser cookies from a signed-in browser.
- Some lectures only show slides through a room camera; the current app extracts the best distinct frames but does not yet provide a manual crop/review editor.
- Narrative notes require English YouTube captions.
- AI narratives require internet access, an OpenAI API key, and API token usage.
