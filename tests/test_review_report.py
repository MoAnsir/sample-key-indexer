from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sample_key_indexer.index_store import SQLiteMetadataIndex, load_records
from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.review_report import build_deep_review_plan, build_review_summary, format_deep_review_plan, format_review_summary, rerun_deep_review, select_deep_review_candidates


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

    def test_select_deep_review_candidates_prioritizes_errors_and_disagreements(self) -> None:
        records = [
            AnalysisResult(
                file_path="/samples/ok.wav",
                root_note="C",
                key="C_major",
                confidence=0.9,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/low.wav",
                root_note=None,
                key=None,
                confidence=0.2,
                category="OneShots",
                type="Leads",
                duration=0.5,
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/disagree.wav",
                root_note="D",
                key="D_minor",
                confidence=0.7,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                needs_review=True,
                review_reasons=["engine_root_disagreement"],
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/error.wav",
                root_note=None,
                key=None,
                confidence=0.0,
                category="OneShots",
                type="FX",
                duration=0.0,
                error="decode failed",
            ).to_dict(),
        ]

        candidates = select_deep_review_candidates(records)

        self.assertEqual([candidate["name"] for candidate in candidates], ["error.wav", "disagree.wav", "low.wav"])
        self.assertEqual(candidates[0]["deep_review_reasons"], ["analysis_error"])
        self.assertIn("key_or_root_disagreement", candidates[1]["deep_review_reasons"])

    def test_select_deep_review_candidates_skips_non_harmonic_low_confidence_without_warning_or_error(self) -> None:
        records = [
            AnalysisResult(
                file_path="/samples/dholak.wav",
                root_note=None,
                key=None,
                confidence=0.1,
                category="OneShots",
                type="Perc",
                duration=0.5,
                needs_review=True,
                review_reasons=["engine_root_disagreement"],
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/dholak_warn.wav",
                root_note=None,
                key=None,
                confidence=0.1,
                category="OneShots",
                type="Perc",
                duration=0.5,
                needs_review=True,
                review_reasons=["engine_root_disagreement"],
                analysis_warnings=["short_signal_fft_adjusted"],
            ).to_dict(),
        ]

        candidates = select_deep_review_candidates(records)

        self.assertEqual([candidate["name"] for candidate in candidates], ["dholak_warn.wav"])
        self.assertEqual(candidates[0]["deep_review_reasons"], ["analysis_warnings"])

    def test_build_and_format_deep_review_plan(self) -> None:
        records = [
            AnalysisResult(
                file_path="/samples/loop.wav",
                root_note="B",
                key="B_major",
                confidence=0.5,
                category="Loops",
                type="MelodyLoops",
                duration=8.0,
                needs_review=True,
                review_reasons=["engine_key_disagreement"],
            ).to_dict()
        ]

        plan = build_deep_review_plan(records, low_confidence=0.6)
        report = format_deep_review_plan(plan)

        self.assertEqual(plan["selected"], 1)
        self.assertIn("Deep review candidates: 1", report)
        self.assertIn("- low_confidence: 1", report)
        self.assertIn("loop.wav | B_major | confidence 0.5", report)

    def test_rerun_deep_review_updates_selected_sqlite_record_and_preserves_library_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "Samples" / "loop.wav"
            audio_path.parent.mkdir()
            audio_path.write_bytes(b"audio")
            index_path = root / "metadata_index.sqlite"
            original = AnalysisResult(
                file_path=str(audio_path),
                root_note="A",
                key="A_minor",
                confidence=0.2,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                needs_review=True,
                review_reasons=["engine_key_disagreement"],
                relative_path="Samples/loop.wav",
                library_id="sd_02",
                library_name="SD 02",
                library_root=str(root),
            )
            replacement = AnalysisResult(
                file_path=str(audio_path),
                root_note="A",
                key="A_minor",
                confidence=0.8,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
            )
            index = SQLiteMetadataIndex(index_path)
            try:
                index.upsert(original)
                index.write()
            finally:
                index.close()

            candidates = select_deep_review_candidates(load_records(index_path))
            with patch("sample_key_indexer.review_report.analyze_file", return_value=replacement):
                summary = rerun_deep_review(index_path, candidates, dry_run=False, isolated=False)

            records = load_records(index_path)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["improved_confidence"], 1)
        self.assertEqual(records[0]["classification"]["confidence"], 0.8)
        self.assertEqual(records[0]["library"]["id"], "sd_02")
        self.assertEqual(records[0]["file"]["relative_path"], "Samples/loop.wav")

    def test_rerun_deep_review_retries_worker_crash_with_fast_librosa_fallback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "loop.wav"
            audio_path.write_bytes(b"audio")
            index_path = root / "metadata_index.sqlite"
            original = AnalysisResult(
                file_path=str(audio_path),
                root_note="A",
                key="A_minor",
                confidence=0.2,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                needs_review=True,
            )
            fallback = AnalysisResult(
                file_path=str(audio_path),
                root_note="A",
                key="A_minor",
                confidence=0.55,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                analysis_profile="fast",
                analysis_engines=["librosa"],
            )
            index = SQLiteMetadataIndex(index_path)
            try:
                index.upsert(original)
                index.write()
            finally:
                index.close()

            candidates = select_deep_review_candidates(load_records(index_path))
            with patch("sample_key_indexer.review_report.analyze_candidate", side_effect=[(None, "worker_crash"), (fallback, None)]):
                summary = rerun_deep_review(index_path, candidates, dry_run=False)

            records = load_records(index_path)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["worker_crashes"], 1)
        self.assertEqual(summary["fallback_successes"], 1)
        self.assertEqual(records[0]["analysis"]["profile"], "fast")
        self.assertEqual(records[0]["classification"]["confidence"], 0.55)

    def test_rerun_deep_review_counts_worker_crash_when_fallback_also_crashes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "loop.wav"
            audio_path.write_bytes(b"audio")
            index_path = root / "metadata_index.sqlite"
            original = AnalysisResult(
                file_path=str(audio_path),
                root_note="A",
                key="A_minor",
                confidence=0.2,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                needs_review=True,
            )
            index = SQLiteMetadataIndex(index_path)
            try:
                index.upsert(original)
                index.write()
            finally:
                index.close()

            candidates = select_deep_review_candidates(load_records(index_path))
            with patch("sample_key_indexer.review_report.analyze_candidate", side_effect=[(None, "worker_crash"), (None, "worker_crash")]):
                summary = rerun_deep_review(index_path, candidates, dry_run=False)

            records = load_records(index_path)

        self.assertEqual(summary["processed"], 0)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["worker_crashes"], 2)
        self.assertEqual(records[0]["classification"]["confidence"], 0.2)


if __name__ == "__main__":
    unittest.main()
