from __future__ import annotations

import unittest

from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.review_report import build_review_summary, format_review_summary


class ReviewReportTests(unittest.TestCase):
    def test_build_review_summary_counts_reasons_and_examples(self) -> None:
        records = [
            AnalysisResult(
                file_path="/samples/a.wav",
                root_note="A",
                key="A_major",
                confidence=0.7,
                category="Loops",
                type="MelodyLoops",
                duration=8.0,
                needs_review=True,
                review_reasons=["filename_key_disagreement"],
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/b.wav",
                root_note="B",
                key="B_major",
                confidence=0.5,
                category="Loops",
                type="BassLoops",
                duration=8.0,
                needs_review=True,
                review_reasons=["engine_root_disagreement", "filename_key_disagreement"],
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/c.wav",
                root_note="E",
                key="E_minor",
                confidence=0.9,
                category="Loops",
                type="MelodyLoops",
                duration=8.0,
            ).to_dict(),
        ]

        summary = build_review_summary(records, max_examples=1)

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["needs_review"], 2)
        self.assertEqual(summary["review_percentage"], 66.67)
        self.assertEqual(summary["reasons"], [
            {"reason": "filename_key_disagreement", "count": 2},
            {"reason": "engine_root_disagreement", "count": 1},
        ])
        self.assertEqual(summary["types"], [
            {"type": "MelodyLoops", "count": 1},
            {"type": "BassLoops", "count": 1},
        ])
        self.assertEqual(summary["examples"][0]["name"], "b.wav")

    def test_format_review_summary_prints_human_report(self) -> None:
        report = format_review_summary({
            "total": 1,
            "needs_review": 1,
            "review_percentage": 100.0,
            "reasons": [{"reason": "engine_key_disagreement", "count": 1}],
            "types": [{"type": "MelodyLoops", "count": 1}],
            "examples": [
                {
                    "name": "loop.wav",
                    "key": "B_major",
                    "root": "B",
                    "confidence": 0.5,
                    "reasons": ["engine_key_disagreement"],
                    "path": "/samples/loop.wav",
                }
            ],
        })

        self.assertIn("Total samples: 1", report)
        self.assertIn("Needs review: 1 (100.0%)", report)
        self.assertIn("- engine_key_disagreement: 1", report)
        self.assertIn("loop.wav | B_major | confidence 0.5", report)


if __name__ == "__main__":
    unittest.main()
