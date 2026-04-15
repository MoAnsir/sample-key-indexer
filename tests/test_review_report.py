from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sample_key_indexer.index_store import SQLiteMetadataIndex, load_records
from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.review_report import build_deep_failure_report, build_deep_review_plan, build_review_summary, format_deep_failure_report, format_deep_review_plan, format_deep_review_result, format_review_summary, rerun_deep_review, select_deep_review_candidates, write_deep_failure_csv, write_deep_failure_json, write_deep_review_report


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
                file_path="/samples/Indian Percussion/WAV/Dholak/dholak_path.wav",
                root_note=None,
                key=None,
                confidence=0.1,
                category="Loops",
                type="BassLoops",
                duration=6.0,
                needs_review=True,
                review_reasons=["engine_root_disagreement"],
                relative_path="Indian Percussion/WAV/Dholak/Dholak Loops/Tempo 080/4'4/dholak_path.wav",
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/Indian Percussion/WAV/Dholak/dholak_warn.wav",
                root_note=None,
                key=None,
                confidence=0.1,
                category="OneShots",
                type="BassLoops",
                duration=0.5,
                needs_review=True,
                review_reasons=["engine_root_disagreement"],
                analysis_warnings=["short_signal_fft_adjusted"],
                relative_path="Indian Percussion/WAV/Dholak/dholak_warn.wav",
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/Indian Melodic/Flute/flute.wav",
                root_note=None,
                key=None,
                confidence=0.1,
                category="Loops",
                type="BassLoops",
                duration=4.0,
                needs_review=True,
                review_reasons=["engine_root_disagreement"],
                relative_path="Indian Melodic/Flute/flute.wav",
            ).to_dict(),
        ]

        candidates = select_deep_review_candidates(records)

        self.assertEqual([candidate["name"] for candidate in candidates], ["flute.wav", "dholak_warn.wav"])
        self.assertIn("key_or_root_disagreement", candidates[0]["deep_review_reasons"])
        self.assertEqual(candidates[1]["deep_review_reasons"], ["analysis_warnings"])

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

    def test_deep_review_plan_skips_previous_failures_unless_retrying(self) -> None:
        failed_record = AnalysisResult(
            file_path="/samples/failed.wav",
            root_note=None,
            key=None,
            confidence=0.2,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            needs_review=True,
            review_reasons=["engine_key_disagreement"],
        ).to_dict()
        failed_record["analysis"]["deep_review"] = {"failed": True, "reason": "worker_crash:worker_crash", "attempts": 1}
        records = [
            failed_record,
            AnalysisResult(
                file_path="/samples/new.wav",
                root_note=None,
                key=None,
                confidence=0.25,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                needs_review=True,
                review_reasons=["engine_key_disagreement"],
            ).to_dict(),
        ]

        plan = build_deep_review_plan(records)
        retry_plan = build_deep_review_plan(records, retry_deep_failed=True)

        self.assertEqual([candidate["name"] for candidate in plan["candidates"]], ["new.wav"])
        self.assertEqual(plan["skipped_deep_failed"], 1)
        self.assertIn("Skipped previous deep-review failures: 1", format_deep_review_plan(plan))
        self.assertEqual([candidate["name"] for candidate in retry_plan["candidates"]], ["failed.wav", "new.wav"])
        self.assertTrue(retry_plan["retry_deep_failed"])

    def test_build_and_export_deep_failure_report(self) -> None:
        failed_record = AnalysisResult(
            file_path="/samples/Flute/failed.wav",
            root_note=None,
            key=None,
            confidence=0.2,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            needs_review=True,
            review_reasons=["engine_key_disagreement"],
            relative_path="Flute/failed.wav",
            library_id="sd_02",
            library_name="SD 02",
        ).to_dict()
        failed_record["analysis"]["deep_review"] = {
            "failed": True,
            "reason": "worker_crash:worker_crash",
            "attempts": 2,
            "last_attempt_at": "2026-04-15T12:00:00+00:00",
            "profile": "deep",
            "engines": ["librosa", "essentia"],
            "path": "/mounted/Flute/failed.wav",
        }
        ok_record = AnalysisResult(
            file_path="/samples/ok.wav",
            root_note="C",
            key="C_major",
            confidence=0.9,
            category="Loops",
            type="MelodyLoops",
            duration=12.0,
        ).to_dict()

        with TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "failures.json"
            csv_path = Path(tmp) / "failures.csv"
            report = build_deep_failure_report([failed_record, ok_record])
            text = format_deep_failure_report(report)
            write_deep_failure_json(report, json_path)
            write_deep_failure_csv(report, csv_path)

            self.assertEqual(report["total"], 1)
            self.assertEqual(report["by_reason"], [{"value": "worker_crash:worker_crash", "count": 1}])
            self.assertEqual(report["by_library"], [{"value": "sd_02", "count": 1}])
            self.assertEqual(report["by_duration"], [{"value": "2-5s", "count": 1}])
            self.assertEqual(report["by_path_family"], [{"value": "Flute", "count": 1}])
            self.assertEqual(report["triage_hints"], [
                "All failures are wav files, so this does not look like broad unsupported-format handling.",
                "All failures crashed both the primary worker and fallback worker; treat these as backend stability cases.",
                "Failures are all under 10 seconds, so short melodic phrases should be tested separately from long loops.",
                "Failures happened under the deep librosa+essentia path; next backend test should compare fast/librosa-only or an external harmonic engine.",
            ])
            self.assertIn("Deep review failures: 1 files", text)
            self.assertIn("Path families:", text)
            self.assertIn("- Flute: 1", text)
            self.assertIn("Triage hints:", text)
            self.assertIn("failed.wav | worker_crash:worker_crash | 2-5s | attempts 2", text)
            json_text = json_path.read_text(encoding="utf-8")
            self.assertIn('"total": 1', json_text)
            self.assertIn('"path_family": "Flute"', json_text)
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("name,library_id,library_name,relative_path,file_path,path_family", csv_text)
            self.assertIn("failed.wav,sd_02,SD 02,Flute/failed.wav,/samples/Flute/failed.wav,Flute", csv_text)

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
        self.assertEqual(summary["details"]["fallback_successes"][0]["name"], "loop.wav")
        self.assertEqual(summary["details"]["fallback_successes"][0]["reason"], "worker_crash")
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
        self.assertEqual(summary["marked_failed"], 1)
        self.assertEqual(summary["details"]["errors"][0]["name"], "loop.wav")
        self.assertEqual(summary["details"]["errors"][0]["reason"], "worker_crash:worker_crash")
        self.assertEqual(records[0]["classification"]["confidence"], 0.2)
        self.assertTrue(records[0]["analysis"]["deep_review"]["failed"])
        self.assertEqual(records[0]["analysis"]["deep_review"]["attempts"], 1)

    def test_rerun_deep_review_reports_missing_audio_details(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_path = root / "missing.wav"
            index_path = root / "metadata_index.sqlite"
            original = AnalysisResult(
                file_path=str(missing_path),
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
            summary = rerun_deep_review(index_path, candidates, dry_run=False)

        self.assertEqual(summary["missing"], 1)
        self.assertEqual(summary["details"]["missing"][0]["name"], "missing.wav")
        self.assertEqual(summary["details"]["missing"][0]["reason"], "audio_not_found")

    def test_format_and_write_deep_review_report_include_details(self) -> None:
        with TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "reports" / "deep_review.json"
            summary = {
                "selected": 1,
                "processed": 0,
                "missing": 0,
                "improved_confidence": 0,
                "still_needs_review": 0,
                "errors": 1,
                "worker_crashes": 2,
                "fallback_successes": 0,
                "dry_run": False,
                "details": {
                    "missing": [],
                    "errors": [{"name": "loop.wav", "reason": "worker_crash:worker_crash"}],
                    "fallback_successes": [],
                },
            }

            report = format_deep_review_result(summary)
            write_deep_review_report(summary, report_path)

            self.assertIn("Error examples:", report)
            self.assertIn("loop.wav | worker_crash:worker_crash", report)
            self.assertTrue(report_path.exists())
            self.assertIn('"worker_crashes": 2', report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
