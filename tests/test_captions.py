from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtube_slides.captions import download_english_captions, parse_vtt, transcript_for_range
from youtube_slides.narrative import build_caption_narratives, notes_by_slide_index
from youtube_slides.pipeline import SlideInfo


class CaptionTests(unittest.TestCase):
    def test_download_english_captions_uses_certificate_environment(self) -> None:
        captured_options: dict[str, object] = {}
        captured_env: dict[str, str | None] = {}

        class FakeYoutubeDL:
            def __init__(self, options: dict[str, object]) -> None:
                captured_options.update(options)

            def __enter__(self) -> "FakeYoutubeDL":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def download(self, urls: list[str]) -> None:
                captured_env["SSL_CERT_FILE"] = os.environ.get("SSL_CERT_FILE")
                captured_env["REQUESTS_CA_BUNDLE"] = os.environ.get("REQUESTS_CA_BUNDLE")
                output_template = str(captured_options["outtmpl"])
                Path(output_template.replace("%(ext)s", "en.vtt")).write_text(
                    """WEBVTT

00:00:01.000 --> 00:00:03.000
Caption text.
""",
                    encoding="utf-8",
                )

        fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
        original_module = sys.modules.get("yt_dlp")
        sys.modules["yt_dlp"] = fake_module
        try:
            with TemporaryDirectory() as tmp:
                with patch.dict(os.environ, {}, clear=True):
                    with patch("youtube_slides.captions.resolve_ca_bundle", return_value="/certifi/cacert.pem"):
                        cues = download_english_captions(
                            "https://www.youtube.com/watch?v=example",
                            Path(tmp),
                            cookie_browser="chrome",
                        )
        finally:
            if original_module is None:
                sys.modules.pop("yt_dlp", None)
            else:
                sys.modules["yt_dlp"] = original_module

        self.assertEqual([cue.text for cue in cues], ["Caption text."])
        self.assertEqual(captured_options["cookiesfrombrowser"], ("chrome", None, None, None))
        self.assertEqual(captured_env["SSL_CERT_FILE"], "/certifi/cacert.pem")
        self.assertEqual(captured_env["REQUESTS_CA_BUNDLE"], "/certifi/cacert.pem")

    def test_parse_vtt_and_transcript_range(self) -> None:
        content = """WEBVTT

00:00:01.000 --> 00:00:03.000
<v Speaker>Welcome to the lecture.

00:00:03.000 --> 00:00:05.000
Today we discuss transformers.

00:00:07.000 --> 00:00:09.000
Attention compares queries and keys.
"""
        cues = parse_vtt(content)

        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[0].text, "Welcome to the lecture.")
        self.assertEqual(
            transcript_for_range(cues, 2.0, 6.0),
            "Welcome to the lecture. Today we discuss transformers.",
        )

    def test_build_caption_narratives(self) -> None:
        cues = parse_vtt(
            """WEBVTT

00:00:01.000 --> 00:00:03.000
Tokenization splits raw text into model inputs.

00:00:06.000 --> 00:00:08.000
Attention lets tokens exchange information.
"""
        )
        slides = [
            SlideInfo(1, "slide_001.png", 0.0, "00:00.000", 0, 0, 1, 1, 1, 1, 1, 1, "a"),
            SlideInfo(2, "slide_002.png", 5.0, "00:05.000", 5, 5, 1, 1, 1, 1, 1, 1, "b"),
        ]

        narratives = build_caption_narratives(slides, cues)
        by_index = notes_by_slide_index(narratives)

        self.assertIn("Tokenization splits raw text", " ".join(by_index[1]))
        self.assertIn("Attention lets tokens", " ".join(by_index[2]))


if __name__ == "__main__":
    unittest.main()
