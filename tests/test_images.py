from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtube_slides.images import CropRegion, RgbImage, read_ppm, write_png, write_ppm


class ImageIoTests(unittest.TestCase):
    def test_ppm_round_trip_and_crop(self) -> None:
        image = RgbImage(
            3,
            2,
            bytes(
                [
                    255,
                    0,
                    0,
                    0,
                    255,
                    0,
                    0,
                    0,
                    255,
                    10,
                    20,
                    30,
                    40,
                    50,
                    60,
                    70,
                    80,
                    90,
                ]
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.ppm"
            write_ppm(path, image)
            loaded = read_ppm(path)

        self.assertEqual(loaded, image)
        cropped = loaded.crop(CropRegion(1, 0, 2, 2))
        self.assertEqual(cropped.width, 2)
        self.assertEqual(cropped.height, 2)
        self.assertEqual(cropped.pixel(0, 0), (0, 255, 0))
        self.assertEqual(cropped.pixel(1, 1), (70, 80, 90))

    def test_write_png_signature(self) -> None:
        image = RgbImage(1, 1, bytes([12, 34, 56]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pixel.png"
            write_png(path, image)
            data = path.read_bytes()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", data)
        self.assertIn(b"IDAT", data)
        self.assertIn(b"IEND", data)


if __name__ == "__main__":
    unittest.main()
