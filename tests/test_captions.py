from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtube_slides.captions import parse_vtt, transcript_for_range
from youtube_slides.narrative import build_caption_narratives, notes_by_slide_index
from youtube_slides.pipeline import SlideInfo


class CaptionTests(unittest.TestCase):
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
