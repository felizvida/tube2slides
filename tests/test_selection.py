from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtube_slides.fingerprint import analyze_image, fingerprints_are_similar
from youtube_slides.images import RgbImage
from youtube_slides.pipeline import format_timestamp, parse_timestamp
from youtube_slides.selection import AnalyzedFrame, select_slide_frames


def synthetic_slide(*, title_bar: int, accent: tuple[int, int, int]) -> RgbImage:
    width = 320
    height = 180
    pixels = bytearray([246, 246, 242] * width * height)

    def rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(y0, y1):
            for x in range(x0, x1):
                offset = (y * width + x) * 3
                pixels[offset : offset + 3] = bytes(color)

    rect(0, 0, width, 22, accent)
    rect(24, 45, 24 + title_bar, 56, (20, 24, 28))
    for y in [82, 104, 126]:
        rect(38, y, 270, y + 6, (42, 48, 56))
    rect(38, 148, 145, 154, accent)
    return RgbImage(width, height, bytes(pixels))


class SelectionTests(unittest.TestCase):
    def test_fingerprints_group_similar_slides(self) -> None:
        first = analyze_image(synthetic_slide(title_bar=140, accent=(20, 110, 180)))
        near_duplicate = analyze_image(synthetic_slide(title_bar=142, accent=(20, 110, 180)))
        different = analyze_image(synthetic_slide(title_bar=90, accent=(180, 70, 40)))

        self.assertTrue(
            fingerprints_are_similar(first, near_duplicate, hash_threshold=20, thumb_threshold=10)
        )
        self.assertFalse(
            fingerprints_are_similar(first, different, hash_threshold=20, thumb_threshold=10)
        )

    def test_select_slide_frames_clusters_adjacent_duplicates(self) -> None:
        slide_a = analyze_image(synthetic_slide(title_bar=140, accent=(20, 110, 180)))
        slide_b = analyze_image(synthetic_slide(title_bar=90, accent=(180, 70, 40)))
        frames = [
            AnalyzedFrame(Path("a1.ppm"), 1, 0.0, slide_a),
            AnalyzedFrame(Path("a2.ppm"), 2, 2.0, slide_a),
            AnalyzedFrame(Path("b1.ppm"), 3, 4.0, slide_b),
            AnalyzedFrame(Path("b2.ppm"), 4, 6.0, slide_b),
        ]
        clusters = select_slide_frames(
            frames,
            min_slide_score=0.0,
            min_stable_samples=2,
            similarity_threshold=20,
            thumb_threshold=10,
            allow_repeats=False,
        )

        self.assertEqual(len(clusters), 2)
        self.assertEqual(len(clusters[0].frames), 2)
        self.assertEqual(len(clusters[1].frames), 2)

    def test_reappearing_duplicate_keeps_first_occurrence(self) -> None:
        slide_a = analyze_image(synthetic_slide(title_bar=140, accent=(20, 110, 180)))
        slide_b = analyze_image(synthetic_slide(title_bar=90, accent=(180, 70, 40)))
        frames = [
            AnalyzedFrame(Path("a1.ppm"), 1, 0.0, slide_a),
            AnalyzedFrame(Path("a2.ppm"), 2, 2.0, slide_a),
            AnalyzedFrame(Path("b1.ppm"), 3, 4.0, slide_b),
            AnalyzedFrame(Path("b2.ppm"), 4, 6.0, slide_b),
            AnalyzedFrame(Path("a3.ppm"), 5, 8.0, slide_a),
            AnalyzedFrame(Path("a4.ppm"), 6, 10.0, slide_a),
        ]

        clusters = select_slide_frames(
            frames,
            min_slide_score=0.0,
            min_stable_samples=2,
            similarity_threshold=20,
            thumb_threshold=10,
            allow_repeats=False,
        )

        self.assertEqual([cluster.frames[0].timestamp for cluster in clusters], [0.0, 4.0])

    def test_timestamp_parsing_and_formatting(self) -> None:
        self.assertEqual(parse_timestamp("01:02:03.5"), 3723.5)
        self.assertEqual(parse_timestamp("02:03"), 123.0)
        self.assertEqual(format_timestamp(3723.5), "01:02:03.500")
        self.assertEqual(format_timestamp(123.0), "02:03.000")


if __name__ == "__main__":
    unittest.main()
