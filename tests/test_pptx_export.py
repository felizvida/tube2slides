from __future__ import annotations

import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtube_slides.pptx_export import _notes_slide_xml


class PptxExportTests(unittest.TestCase):
    def test_notes_slide_xml_escapes_text(self) -> None:
        xml = _notes_slide_xml(["Narrative:", "A < B & C > D"])
        root = ET.fromstring(xml)
        text = "".join(root.itertext())

        self.assertIn("Narrative:", text)
        self.assertIn("A < B & C > D", text)


if __name__ == "__main__":
    unittest.main()
