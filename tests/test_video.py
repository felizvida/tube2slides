from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtube_slides.video import _download_with_ytdlp


class VideoDownloadTests(unittest.TestCase):
    def test_bundled_ytdlp_api_fallback_writes_download(self) -> None:
        captured_options: dict[str, object] = {}
        captured_urls: list[str] = []
        captured_env: dict[str, str | None] = {}

        class FakeYoutubeDL:
            def __init__(self, options: dict[str, object]) -> None:
                captured_options.update(options)

            def __enter__(self) -> "FakeYoutubeDL":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def download(self, urls: list[str]) -> None:
                captured_urls.extend(urls)
                captured_env["SSL_CERT_FILE"] = os.environ.get("SSL_CERT_FILE")
                captured_env["REQUESTS_CA_BUNDLE"] = os.environ.get("REQUESTS_CA_BUNDLE")
                output_template = str(captured_options["outtmpl"])
                Path(output_template.replace("%(ext)s", "mp4")).write_bytes(b"video")

        fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        original_module = sys.modules.get("yt_dlp")
        sys.modules["yt_dlp"] = fake_module
        try:
            with TemporaryDirectory() as tmp:
                with patch.dict(os.environ, {}, clear=True):
                    with patch("youtube_slides.video.shutil.which", return_value=None):
                        with patch("youtube_slides.video.resolve_ca_bundle", return_value="/certifi/cacert.pem"):
                            with patch(
                                "youtube_slides.video.resolve_ffmpeg_executable",
                                return_value="/bundled/ffmpeg",
                            ):
                                downloaded = _download_with_ytdlp(
                                    "https://www.youtube.com/watch?v=example",
                                    Path(tmp),
                                    ytdlp="yt-dlp",
                                    cookie_browser="chrome",
                                )
        finally:
            if original_module is None:
                sys.modules.pop("yt_dlp", None)
            else:
                sys.modules["yt_dlp"] = original_module

        self.assertIsNotNone(downloaded)
        self.assertEqual(downloaded.name, "source.mp4")
        self.assertEqual(captured_urls, ["https://www.youtube.com/watch?v=example"])
        self.assertEqual(captured_options["ffmpeg_location"], "/bundled/ffmpeg")
        self.assertEqual(captured_options["cookiesfrombrowser"], ("chrome", None, None, None))
        self.assertEqual(captured_env["SSL_CERT_FILE"], "/certifi/cacert.pem")
        self.assertEqual(captured_env["REQUESTS_CA_BUNDLE"], "/certifi/cacert.pem")

    def test_external_ytdlp_receives_certificate_environment(self) -> None:
        captured_extra_env: dict[str, str] = {}
        captured_command: list[str] = []

        def fake_run(command: list[str], *, description: str, extra_env: dict[str, str] | None = None) -> None:
            self.assertEqual(description, "download video with yt-dlp")
            captured_command.extend(command)
            output_index = command.index("-o") + 1
            Path(command[output_index].replace("%(ext)s", "mp4")).write_bytes(b"video")
            captured_extra_env.update(extra_env or {})

        with TemporaryDirectory() as tmp:
            with patch("youtube_slides.video.shutil.which", return_value="/usr/bin/yt-dlp"):
                with patch("youtube_slides.video.resolve_ca_bundle", return_value="/certifi/cacert.pem"):
                    with patch("youtube_slides.video.resolve_ffmpeg_executable", return_value="/bundled/ffmpeg"):
                        with patch("youtube_slides.video._run", side_effect=fake_run):
                            downloaded = _download_with_ytdlp(
                                "https://www.youtube.com/watch?v=example",
                                Path(tmp),
                                ytdlp="yt-dlp",
                                cookie_browser="chrome",
                            )

        self.assertIsNotNone(downloaded)
        self.assertEqual(downloaded.name, "source.mp4")
        self.assertIn("--cookies-from-browser", captured_command)
        self.assertIn("chrome", captured_command)
        self.assertEqual(captured_extra_env["SSL_CERT_FILE"], "/certifi/cacert.pem")
        self.assertEqual(captured_extra_env["REQUESTS_CA_BUNDLE"], "/certifi/cacert.pem")


if __name__ == "__main__":
    unittest.main()
