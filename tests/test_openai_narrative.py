from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtube_slides.openai_narrative import extract_response_text, parse_narrative_json


class OpenAiNarrativeTests(unittest.TestCase):
    def test_extracts_direct_output_text(self) -> None:
        response = {"output_text": '{"slides":[]}'}

        self.assertEqual(extract_response_text(response), '{"slides":[]}')

    def test_extracts_nested_output_text(self) -> None:
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"slides":[{"slide_index":1,"notes":["Explain the setup."]}]}',
                        }
                    ],
                }
            ]
        }

        self.assertIn("Explain the setup", extract_response_text(response))

    def test_parses_fenced_json(self) -> None:
        parsed = parse_narrative_json(
            '```json\n{"slides":[{"slide_index":2,"notes":["Attention compares tokens."]}]}\n```'
        )

        self.assertEqual(parsed[0]["slide_index"], 2)
        self.assertEqual(parsed[0]["notes"][0], "Attention compares tokens.")


if __name__ == "__main__":
    unittest.main()
