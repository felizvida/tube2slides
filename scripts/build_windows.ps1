$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

py -3 -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install --upgrade pip
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop.txt

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

.\.venv-desktop\Scripts\pyinstaller.exe `
  --noconfirm `
  --windowed `
  --name "YouTube Lecture Slides" `
  --collect-all imageio_ffmpeg `
  --collect-all yt_dlp `
  --hidden-import pptx `
  packaging\desktop_launcher.py

Write-Host "Built dist\YouTube Lecture Slides\YouTube Lecture Slides.exe"
