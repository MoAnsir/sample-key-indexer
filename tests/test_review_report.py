from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sample_key_indexer.index_store import SQLiteMetadataIndex, load_records
from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.review_report import build_backend_check_report, build_classification_audit_report, build_deep_failure_report, build_deep_review_plan, build_keyfinder_comparison_report, build_keyfinder_experiment_report, build_review_summary, enrich_keyfinder_metadata, format_backend_check_report, format_classification_audit_report, format_deep_failure_report, format_deep_review_plan, format_deep_review_result, format_keyfinder_comparison_report, format_keyfinder_experiment_report, format_review_summary, keyfinder_targets, rerun_deep_review, run_keyfinder_with_converted_wav, select_deep_review_candidates, write_classification_audit_csv, write_classification_audit_json, write_deep_failure_csv, write_deep_failure_json, write_deep_review_report


class ReviewReportTests(unittest.TestCase):
    def test_classification_audit_flags_suspicious_filename_type_mismatches(self) -> None:
        records = [
            AnalysisResult(
                file_path="/samples/Melodies/Drum_Beat_90.wav",
                root_note=None,
                key=None,
                confidence=0.5,
                relative_path="Melodies/Drum_Beat_90.wav",
                category="Loops",
                type="MelodyLoops",
                duration=8.0,
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/Kicks/HH_Open_01.wav",
                root_note=None,
                key=None,
                confidence=0.5,
                relative_path="Kicks/HH_Open_01.wav",
                category="OneShots",
                type="Kick",
                duration=0.4,
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/Loops/Pack_FullMix_128.wav",
                root_note=None,
                key=None,
                confidence=0.5,
                relative_path="Loops/Pack_FullMix_128.wav",
                category="Loops",
                type="MelodyLoops",
                duration=90.0,
            ).to_dict(),
            AnalysisResult(
                file_path="/samples/Kicks/Hard_Kick_01.wav",
                root_note=None,
                key=None,
                confidence=0.5,
                relative_path="Kicks/Hard_Kick_01.wav",
                category="OneShots",
                type="Kick",
                duration=0.4,
            ).to_dict(),
        ]

        report = build_classification_audit_report(records, max_examples=10)

        self.assertEqual(report["total"], 4)
        self.assertEqual(report["suspicious"], 3)
        reasons = {item["value"]: item["count"] for item in report["by_reason"]}
        self.assertEqual(reasons["drum_loop_misclassified"], 1)
        self.assertEqual(reasons["type_mismatch_from_filename"], 1)
        self.assertEqual(reasons["ignored_fullmix_present"], 1)
        names = {item["name"] for item in report["examples"]}
        self.assertIn("Drum_Beat_90.wav", names)
        self.assertIn("HH_Open_01.wav", names)
        self.assertIn("Pack_FullMix_128.wav", names)
        self.assertNotIn("Hard_Kick_01.wav", names)

    def test_format_classification_audit_prints_human_report(self) -> None:
        report = {
            "total": 1,
            "suspicious": 1,
            "by_reason": [{"value": "drum_loop_misclassified", "count": 1}],
            "by_library": [{"value": "usb_01", "count": 1}],
            "by_type": [{"value": "MelodyLoops", "count": 1}],
            "by_path_family": [{"value": "SAMPLEZ / Pack", "count": 1}],
            "examples": [
                {
                    "name": "Drum_Beat_90.wav",
                    "stored_category": "Loops",
                    "stored_type": "MelodyLoops",
                    "suggested_category": "Loops",
                    "suggested_type": "DrumLoops",
                    "reasons": ["drum_loop_misclassified"],
                }
            ],
        }

        output = format_classification_audit_report(report)

        self.assertIn("Classification audit:", output)
        self.assertIn("Suspicious classifications: 1 files", output)
        self.assertIn("- drum_loop_misclassified: 1", output)
        self.assertIn("Drum_Beat_90.wav | stored Loops/MelodyLoops", output)

    def test_write_classification_audit_exports_json_and_csv(self) -> None:
        report = {
            "total": 1,
            "suspicious": 1,
            "by_reason": [],
            "by_library": [],
            "by_type": [],
            "by_path_family": [],
            "examples": [],
            "items": [
                {
                    "name": "Pack_FullMix_128.wav",
                    "library_id": "usb_01",
                    "library_name": "USB 01",
                    "relative_path": "Loops/Pack_FullMix_128.wav",
                    "file_path": "/samples/Loops/Pack_FullMix_128.wav",
                    "path_family": "Loops",
                    "stored_category": "Loops",
                    "stored_type": "MelodyLoops",
                    "suggested_category": None,
                    "suggested_type": None,
                    "confidence": 0.8,
                    "duration": 90.0,
                    "reasons": ["ignored_fullmix_present"],
                }
            ],
        }
        with TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "classification.json"
            csv_path = Path(tmp) / "classification.csv"

            write_classification_audit_json(report, json_path)
            write_classification_audit_csv(report, csv_path)

            self.assertIn("ignored_fullmix_present", json_path.read_text())
            self.assertIn("Pack_FullMix_128.wav", csv_path.read_text())

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

    def test_backend_check_report_includes_targets_and_backend_status(self) -> None:
        failed_record = AnalysisResult(
            file_path="/samples/Indian Melodic/Flute/failed.wav",
            root_note=None,
            key=None,
            confidence=0.2,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            needs_review=True,
            relative_path="Indian Melodic/Flute/failed.wav",
        ).to_dict()
        failed_record["analysis"]["deep_review"] = {
            "failed": True,
            "reason": "worker_crash:worker_crash",
            "attempts": 1,
            "profile": "deep",
            "engines": ["librosa", "essentia"],
        }
        backend_status = {
            "commands": [
                {
                    "id": "keyfinder",
                    "label": "KeyFinder CLI",
                    "status": "missing",
                    "path": None,
                    "version": None,
                    "purpose": "External harmonic key detection.",
                },
                {
                    "id": "sonic_annotator",
                    "label": "Sonic Annotator",
                    "status": "available",
                    "path": "/usr/local/bin/sonic-annotator",
                    "version": "Sonic Annotator 1.6",
                    "purpose": "Vamp plugin runner for QM key/chord plugins.",
                },
            ],
            "qm_vamp_plugins": {
                "status": "available",
                "matches": ["/Library/Audio/Plug-Ins/Vamp/qm-vamp-plugins.dylib"],
                "searched": [],
            },
        }

        with patch("sample_key_indexer.review_report.discover_deep_backends", return_value=backend_status):
            report = build_backend_check_report([failed_record])
        text = format_backend_check_report(report)

        self.assertEqual(report["deep_failure_targets"]["total"], 1)
        self.assertEqual(report["deep_failure_targets"]["by_path_family"], [{"value": "Indian Melodic / Flute", "count": 1}])
        self.assertIn("Deep backend check:", text)
        self.assertIn("Deep-review failure targets: 1 files", text)
        self.assertIn("Sonic Annotator: available (/usr/local/bin/sonic-annotator)", text)
        self.assertIn("QM Vamp Plugins: available", text)

    def test_keyfinder_comparison_report_groups_stored_external_metadata(self) -> None:
        match = AnalysisResult(
            file_path="/samples/match.wav",
            root_note="C",
            key="C_major",
            confidence=0.82,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            library_id="sd_01",
            library_name="SD 01",
        ).to_dict()
        match["analysis"]["external"] = {
            "keyfinder": {
                "status": "success",
                "normalized_key": "C_major",
                "root_note": "C",
                "matches_stored_key": True,
                "matches_stored_root": True,
                "conversion_used": False,
            }
        }
        root_only = AnalysisResult(
            file_path="/samples/root.wav",
            root_note="D",
            key="D_minor",
            confidence=0.62,
            category="Loops",
            type="BassLoops",
            duration=4.0,
            format="wav",
            library_id="sd_01",
            library_name="SD 01",
        ).to_dict()
        root_only["analysis"]["external"] = {
            "keyfinder": {
                "status": "success",
                "normalized_key": "D_major",
                "root_note": "D",
                "matches_stored_key": False,
                "matches_stored_root": True,
                "conversion_used": True,
            }
        }
        disagreement = AnalysisResult(
            file_path="/samples/disagree.wav",
            root_note="F",
            key="F_minor",
            confidence=0.9,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            library_id="sd_02",
            library_name="SD 02",
        ).to_dict()
        disagreement["analysis"]["external"] = {
            "keyfinder": {
                "status": "success",
                "normalized_key": "A_major",
                "root_note": "A",
                "matches_stored_key": False,
                "matches_stored_root": False,
                "conversion_used": False,
            }
        }
        missing = AnalysisResult(
            file_path="/samples/missing.wav",
            root_note="G",
            key="G_major",
            confidence=0.4,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            library_id="sd_02",
            library_name="SD 02",
        ).to_dict()

        report = build_keyfinder_comparison_report([match, root_only, disagreement, missing], max_examples=5)
        text = format_keyfinder_comparison_report(report)

        self.assertEqual(report["total"], 4)
        self.assertEqual(report["enriched"], 3)
        self.assertEqual(report["missing_keyfinder"], 1)
        self.assertEqual(report["matches_stored_key"], 1)
        self.assertEqual(report["matches_stored_root"], 2)
        self.assertEqual(report["root_only_matches"], 1)
        self.assertEqual(report["key_and_root_disagreements"], 1)
        self.assertEqual(report["conversion_used"], 1)
        self.assertEqual(report["by_decision"], [
            {"value": "key_match", "count": 1},
            {"value": "root_match_key_diff", "count": 1},
            {"value": "key_and_root_disagree", "count": 1},
        ])
        self.assertEqual(report["disagreement_examples"][0]["name"], "disagree.wav")
        self.assertIn("KeyFinder comparison:", text)
        self.assertIn("With KeyFinder metadata: 3 files", text)
        self.assertIn("By library:", text)
        self.assertIn("disagree.wav | sd_02", text)

    def test_keyfinder_experiment_reports_successes_and_errors(self) -> None:
        failed_a = AnalysisResult(
            file_path="/samples/a.wav",
            root_note="F",
            key="F_minor",
            confidence=0.2,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            needs_review=True,
        ).to_dict()
        failed_a["analysis"]["deep_review"] = {"failed": True, "reason": "worker_crash:worker_crash"}
        failed_b = AnalysisResult(
            file_path="/samples/b.wav",
            root_note="A",
            key="A_major",
            confidence=0.2,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            needs_review=True,
        ).to_dict()
        failed_b["analysis"]["deep_review"] = {"failed": True, "reason": "worker_crash:worker_crash"}

        with patch("sample_key_indexer.review_report.shutil.which", return_value="/usr/local/bin/keyfinder-cli"):
            with patch("sample_key_indexer.review_report.Path.exists", return_value=True):
                with patch("sample_key_indexer.review_report.run_keyfinder", side_effect=[
                    {"status": "success", "raw_key": "Fm", "normalized_key": "F_minor", "root_note": "F", "raw_output": "Fm", "error": None},
                    {"status": "error", "error": "Unable to resample audio into 16bit PCM data", "raw_output": "Unable to resample audio into 16bit PCM data"},
                ]):
                    report = build_keyfinder_experiment_report([failed_a, failed_b])
        text = format_keyfinder_experiment_report(report)

        self.assertEqual(report["selected"], 2)
        self.assertEqual(report["scope"], "failures")
        self.assertEqual(report["processed"], 1)
        self.assertEqual(report["successes"], 1)
        self.assertEqual(report["errors"], 1)
        self.assertEqual(report["matches_stored_key"], 1)
        self.assertEqual(report["error_reasons"], [{"value": "Unable to resample audio into 16bit PCM data", "count": 1}])
        self.assertEqual(report["success_by_path_family"], [{"value": "samples", "count": 1}])
        self.assertEqual(report["error_by_path_family"], [{"value": "samples", "count": 1}])
        self.assertIn("KeyFinder experiment:", text)
        self.assertIn("Scope: failures", text)
        self.assertIn("Selected samples: 2 files", text)
        self.assertIn("Error reasons:", text)
        self.assertIn("a.wav | KeyFinder Fm (F_minor)", text)
        self.assertIn("b.wav | error | Unable to resample audio into 16bit PCM data", text)

    def test_keyfinder_experiment_can_target_full_index(self) -> None:
        record_a = AnalysisResult(
            file_path="/samples/a.wav",
            root_note="C",
            key="C_major",
            confidence=0.8,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
        ).to_dict()
        record_b = AnalysisResult(
            file_path="/samples/b.wav",
            root_note="D",
            key="D_minor",
            confidence=0.7,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
        ).to_dict()

        with patch("sample_key_indexer.review_report.shutil.which", return_value="/usr/local/bin/keyfinder-cli"):
            with patch("sample_key_indexer.review_report.Path.exists", return_value=True):
                with patch("sample_key_indexer.review_report.run_keyfinder", side_effect=[
                    {"status": "success", "raw_key": "C", "normalized_key": "C_major", "root_note": "C", "raw_output": "C", "error": None},
                    {"status": "success", "raw_key": "Dm", "normalized_key": "D_minor", "root_note": "D", "raw_output": "Dm", "error": None},
                ]):
                    report = build_keyfinder_experiment_report([record_a, record_b], scope="all")

        self.assertEqual(report["scope"], "all")
        self.assertEqual(report["selected"], 2)
        self.assertEqual(report["processed"], 2)
        self.assertEqual(report["matches_stored_key"], 2)
        self.assertEqual(report["matches_stored_root"], 2)

    def test_keyfinder_experiment_can_retry_with_converted_wav(self) -> None:
        failed_record = AnalysisResult(
            file_path="/samples/a.wav",
            root_note="C",
            key="C_major",
            confidence=0.2,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            needs_review=True,
        ).to_dict()
        failed_record["analysis"]["deep_review"] = {"failed": True, "reason": "worker_crash:worker_crash"}

        with patch("sample_key_indexer.review_report.shutil.which", side_effect=lambda command: f"/usr/local/bin/{command}"):
            with patch("sample_key_indexer.review_report.Path.exists", return_value=True):
                with patch("sample_key_indexer.review_report.run_keyfinder", return_value={
                    "status": "error",
                    "error": "Unable to resample audio into 16bit PCM data",
                    "raw_output": "Unable to resample audio into 16bit PCM data",
                }):
                    with patch("sample_key_indexer.review_report.run_keyfinder_with_converted_wav", return_value={
                        "status": "success",
                        "raw_key": "C",
                        "normalized_key": "C_major",
                        "root_note": "C",
                        "raw_output": "C",
                        "error": None,
                        "conversion_status": "success",
                        "conversion_error": None,
                    }):
                        report = build_keyfinder_experiment_report([failed_record], convert_retry=True)
        text = format_keyfinder_experiment_report(report)

        self.assertTrue(report["convert_retry"])
        self.assertEqual(report["conversion_attempts"], 1)
        self.assertEqual(report["conversion_successes"], 1)
        self.assertEqual(report["successes"], 1)
        self.assertEqual(report["errors"], 0)
        self.assertIn("Conversion retry: on", text)

    def test_run_keyfinder_with_converted_wav_reports_ffmpeg_failure(self) -> None:
        with patch("sample_key_indexer.review_report.convert_to_pcm16_wav", return_value={"status": "error", "error": "ffmpeg_failed", "raw_output": "bad file"}):
            result = run_keyfinder_with_converted_wav("/usr/local/bin/keyfinder-cli", Path("/samples/a.wav"), "/opt/homebrew/bin/ffmpeg")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["conversion_status"], "error")
        self.assertEqual(result["conversion_error"], "ffmpeg_failed")

    def test_keyfinder_failure_targets_keep_structured_records_for_enrichment(self) -> None:
        failed_record = AnalysisResult(
            file_path="/samples/a.wav",
            root_note="C",
            key="C_major",
            confidence=0.2,
            category="Loops",
            type="MelodyLoops",
            duration=4.0,
            format="wav",
            needs_review=True,
        ).to_dict()
        failed_record["analysis"]["deep_review"] = {"failed": True, "reason": "worker_crash:worker_crash"}

        targets = keyfinder_targets([failed_record], scope="failures")

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["name"], "a.wav")
        self.assertEqual(targets[0]["structured"]["file"]["path"], "/samples/a.wav")

    def test_keyfinder_enrichment_stores_external_signal_without_changing_main_key(self) -> None:
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
                confidence=0.8,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                format="wav",
                relative_path="Samples/loop.wav",
                library_id="sd_02",
                library_name="SD 02",
            )
            index = SQLiteMetadataIndex(index_path)
            try:
                index.upsert(original)
                index.write()
            finally:
                index.close()

            with patch("sample_key_indexer.review_report.shutil.which", side_effect=lambda command: f"/usr/local/bin/{command}"):
                with patch("sample_key_indexer.review_report.run_keyfinder", return_value={
                    "status": "success",
                    "raw_key": "C",
                    "normalized_key": "C_major",
                    "root_note": "C",
                    "raw_output": "C",
                    "error": None,
                }):
                    summary = enrich_keyfinder_metadata(index_path, load_records(index_path), scope="all", write_every=1)

            records = load_records(index_path)

        external = records[0]["analysis"]["external"]["keyfinder"]
        self.assertEqual(summary["selected"], 1)
        self.assertEqual(summary["updated"], 1)
        self.assertEqual(summary["matches_stored_key"], 0)
        self.assertEqual(external["raw_key"], "C")
        self.assertEqual(external["normalized_key"], "C_major")
        self.assertFalse(external["matches_stored_key"])
        self.assertEqual(records[0]["musical"]["key"], "A_minor")
        self.assertEqual(records[0]["musical"]["root"], "A")

    def test_keyfinder_enrichment_dry_run_does_not_write_external_signal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "loop.wav"
            audio_path.write_bytes(b"audio")
            index_path = root / "metadata_index.sqlite"
            original = AnalysisResult(
                file_path=str(audio_path),
                root_note="C",
                key="C_major",
                confidence=0.8,
                category="Loops",
                type="MelodyLoops",
                duration=4.0,
                format="wav",
            )
            index = SQLiteMetadataIndex(index_path)
            try:
                index.upsert(original)
                index.write()
            finally:
                index.close()

            with patch("sample_key_indexer.review_report.shutil.which", return_value="/usr/local/bin/keyfinder-cli"):
                with patch("sample_key_indexer.review_report.run_keyfinder", return_value={
                    "status": "success",
                    "raw_key": "C",
                    "normalized_key": "C_major",
                    "root_note": "C",
                    "raw_output": "C",
                    "error": None,
                }):
                    summary = enrich_keyfinder_metadata(index_path, load_records(index_path), scope="all", dry_run=True)

            records = load_records(index_path)

        self.assertTrue(summary["dry_run"])
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["updated"], 0)
        self.assertNotIn("external", records[0]["analysis"])

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
