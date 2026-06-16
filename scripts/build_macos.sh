#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m venv .venv-desktop
./.venv-desktop/bin/python -m pip install --upgrade pip
./.venv-desktop/bin/python -m pip install -r requirements-desktop.txt

rm -rf build dist

./.venv-desktop/bin/pyinstaller \
  --noconfirm \
  --windowed \
  --name "Slidewright" \
  --collect-all certifi \
  --collect-all imageio_ffmpeg \
  --collect-all yt_dlp \
  --hidden-import pptx \
  packaging/desktop_launcher.py

echo "Built dist/Slidewright.app"
