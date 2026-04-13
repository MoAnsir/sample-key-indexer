from __future__ import annotations

import unittest

from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.web_app import _flatten_sample, summarize_by_type


class WebAppTests(unittest.TestCase):
    def test_summarize_by_type_counts_and_percentages(self) -> None:
        stats = summarize_by_type([
            {"type": "Kick"},
            {"type": "Kick"},
            {"type": "Bass"},
            {"type": "Snare"},
        ])

        self.assertEqual(stats, [
            {"type": "Kick", "count": 2, "percentage": 50.0},
            {"type": "Bass", "count": 1, "percentage": 25.0},
            {"type": "Snare", "count": 1, "percentage": 25.0},
        ])

    def test_structured_result_flattens_for_browser(self) -> None:
        result = AnalysisResult(
            file_path="/samples/pad_dark_em.wav",
            root_note="E",
            key="E_minor",
            confidence=0.82,
            category="Loops",
            type="MelodyLoops",
            duration=3.2,
            sample_rate=44100,
            notes=["E", "G", "B"],
            brightness="medium",
            source="synth",
            destination="/organised/Key/E_minor/Loops/MelodyLoops/pad_dark_em.wav",
        )

        sample = _flatten_sample(result.to_dict())

        self.assertEqual(sample["file_path"], "/samples/pad_dark_em.wav")
        self.assertEqual(sample["root_note"], "E")
        self.assertEqual(sample["key"], "E_minor")
        self.assertEqual(sample["type"], "MelodyLoops")
        self.assertEqual(sample["notes"], ["E", "G", "B"])
        self.assertEqual(sample["brightness"], "medium")
        self.assertEqual(sample["source"], "synth")


if __name__ == "__main__":
    unittest.main()
