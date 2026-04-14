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
            essentia_key="E_minor",
            filename_key="C_minor",
            analysis_profile="balanced",
            analysis_engines=["librosa", "essentia"],
            needs_review=True,
            review_reasons=["filename_key_disagreement"],
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
        self.assertEqual(sample["analysis_profile"], "balanced")
        self.assertEqual(sample["analysis_engines"], ["librosa", "essentia"])
        self.assertEqual(sample["essentia_key"], "E_minor")
        self.assertEqual(sample["filename_key"], "C_minor")
        self.assertTrue(sample["needs_review"])
        self.assertEqual(sample["review_reasons"], ["filename_key_disagreement"])

    def test_programs_keep_raw_engine_keys(self) -> None:
        result = AnalysisResult(
            file_path="/samples/accordion.wav",
            root_note="G",
            key="G_minor",
            confidence=0.62,
            category="Loops",
            type="MelodyLoops",
            duration=8.5,
            librosa_root="G",
            librosa_key=None,
            librosa_key_confidence=0.947,
            essentia_root="G",
            essentia_key="G_minor",
            essentia_key_confidence=0.73,
        )

        programs = result.to_dict()["analysis"]["programs"]

        self.assertIsNone(programs["librosa"]["key"])
        self.assertEqual(programs["essentia"]["key"], "G_minor")


if __name__ == "__main__":
    unittest.main()
