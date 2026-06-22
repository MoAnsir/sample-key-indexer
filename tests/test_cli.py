from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from io import StringIO
from contextlib import redirect_stdout
import unittest
from concurrent.futures.process import BrokenProcessPool
from unittest.mock import patch

from sample_key_indexer.audio_analysis import AudioProbe
from sample_key_indexer.cli import AnalysisRunSummary, FileTypeSummary, ProbeRunSummary, analyze_file_isolated, attach_library_metadata, format_gb, missing_required_external_tools, normalize_crash_signature, print_copy_report, slugify, split_ignored_files, summarize_paths_by_extension, summarize_unsupported_files, split_long_files, update_analysis_summary, worker_crash_result, write_run_report
from sample_key_indexer.models import AnalysisResult


class CliTests(unittest.TestCase):
    def test_missing_required_external_tools_checks_keyfinder(self) -> None:
        with patch("sample_key_indexer.cli.shutil.which", return_value=None):
            self.assertEqual(missing_required_external_tools(), [("keyfinder-cli", "keyfinder")])

        with patch("sample_key_indexer.cli.shutil.which", side_effect=lambda command: "/usr/local/bin/keyfinder-cli" if command == "keyfinder-cli" else None):
            self.assertEqual(missing_required_external_tools(), [])

    def test_split_ignored_files_skips_fullmix_names(self) -> None:
        paths = [
            Path("Loops/PL_pack_FullMix_128_C.wav"),
            Path("Loops/PL pack full mix master.wav"),
            Path("Loops/artist_music-loop_demo.wav"),
            Path("Loops/artist_musicloop_demo.wav"),
            Path("Loops/drum_loop_128.wav"),
        ]

        processable, skipped = split_ignored_files(paths)

        self.assertEqual(processable, [Path("Loops/drum_loop_128.wav")])
        self.assertEqual(
            skipped,
            [
                Path("Loops/PL_pack_FullMix_128_C.wav"),
                Path("Loops/PL pack full mix master.wav"),
                Path("Loops/artist_music-loop_demo.wav"),
                Path("Loops/artist_musicloop_demo.wav"),
            ],
        )

    def test_split_long_files_skips_above_threshold(self) -> None:
        paths = [Path("short.wav"), Path("song.wav"), Path("unknown.wav")]
        probes = {
            Path("short.wav"): AudioProbe(duration=12.0, backend="ffprobe"),
            Path("song.wav"): AudioProbe(duration=180.0, backend="ffprobe"),
            Path("unknown.wav"): AudioProbe(duration=None, backend="python", error="decode failed"),
        }

        with patch("sample_key_indexer.audio_analysis.probe_audio_file", side_effect=lambda path, _: probes[path]):
            processable, skipped, summary = split_long_files(paths, 60.0)

        self.assertEqual(processable, [Path("short.wav"), Path("unknown.wav")])
        self.assertEqual(skipped, [Path("song.wav")])
        self.assertEqual(summary.ffprobe, 2)
        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.failed_reason_counts["decode failed"], 1)
        self.assertEqual(summary.failed_examples[0]["path"], "unknown.wav")

    def test_split_long_files_can_be_disabled(self) -> None:
        paths = [Path("song.wav")]
        processable, skipped, summary = split_long_files(paths, 0)

        self.assertEqual(processable, paths)
        self.assertEqual(skipped, [])
        self.assertEqual(summary.ffprobe, 0)

    def test_summarize_unsupported_files_groups_by_extension_and_size(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kick.wav").write_bytes(b"audio")
            (root / "loop.flac").write_bytes(b"12345")
            (root / "cover.jpg").write_bytes(b"123")
            (root / "license").write_bytes(b"12")

            summary = summarize_unsupported_files(root)

        self.assertNotIn(".wav", summary)
        self.assertEqual(summary[".flac"].count, 1)
        self.assertEqual(summary[".flac"].bytes, 5)
        self.assertEqual(summary[".jpg"].count, 1)
        self.assertEqual(summary[".jpg"].bytes, 3)
        self.assertEqual(summary["[no extension]"].count, 1)
        self.assertEqual(summary["[no extension]"].bytes, 2)

    def test_summarize_paths_by_extension_groups_long_skips(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            wav = root / "song.wav"
            mp3 = root / "song.mp3"
            wav.write_bytes(b"1234")
            mp3.write_bytes(b"12")

            summary = summarize_paths_by_extension([wav, mp3])

        self.assertEqual(summary[".wav"].bytes, 4)
        self.assertEqual(summary[".mp3"].bytes, 2)

    def test_format_gb_uses_decimal_gigabytes(self) -> None:
        self.assertEqual(format_gb(1_500_000_000), "1.50 GB")

    def test_attach_library_metadata_stores_relative_path_and_library(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "Kicks" / "kick.wav"
            audio_path.parent.mkdir()
            audio_path.write_bytes(b"audio")
            result = AnalysisResult(
                file_path=str(audio_path),
                root_note="C",
                key="C_major",
                confidence=0.8,
                category="OneShots",
                type="Kick",
                duration=0.4,
            )

            enriched = attach_library_metadata(result, root, "usb_01", "USB 01")

        self.assertEqual(enriched.relative_path, "Kicks/kick.wav")
        self.assertEqual(enriched.library_id, "usb_01")
        self.assertEqual(enriched.library_name, "USB 01")
        self.assertEqual(enriched.library_root, str(root))

    def test_slugify_creates_stable_library_id(self) -> None:
        self.assertEqual(slugify("Samples to Detect!"), "samples_to_detect")

    def test_update_analysis_summary_counts_review_warning_and_error_flags(self) -> None:
        summary = AnalysisRunSummary()
        result = AnalysisResult(
            file_path="/samples/noisy.wav",
            root_note=None,
            key=None,
            confidence=0.2,
            category="OneShots",
            type="FX",
            duration=0.03,
            analysis_warnings=["decoder_fallback_audioread", "tiny_audio"],
            needs_review=True,
            review_reasons=["tiny_audio", "filename_key_disagreement_weak"],
            error="decode failed",
        )

        update_analysis_summary(summary, result)

        self.assertEqual(summary.errors, 1)
        self.assertEqual(summary.needs_review, 1)
        self.assertEqual(summary.low_confidence, 1)
        self.assertEqual(summary.key_disagreements, 1)
        self.assertEqual(summary.decoder_fallbacks, 1)
        self.assertEqual(summary.tiny_audio, 1)
        self.assertEqual(summary.warning_records, 1)
        self.assertEqual(summary.worker_crashes, 0)
        self.assertEqual(len(summary.error_examples), 1)
        self.assertEqual(len(summary.warning_examples), 1)
        self.assertEqual(len(summary.review_examples), 1)

    def test_worker_crash_result_marks_file_for_review(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "kick_loop.wav"
            path.write_bytes(b"audio")

            result = worker_crash_result(path, "balanced", ("librosa", "essentia"), "worker_crash")

        self.assertEqual(result.file_path, str(path))
        self.assertTrue(result.needs_review)
        self.assertEqual(result.review_reasons, ["worker_crash"])
        self.assertEqual(result.error, "worker_crash")
        self.assertEqual(result.analysis_warnings, ["worker_crash"])

    def test_update_analysis_summary_counts_worker_crashes(self) -> None:
        summary = AnalysisRunSummary()
        result = AnalysisResult(
            file_path="/samples/broken.wav",
            root_note=None,
            key=None,
            confidence=0.0,
            category="Loops",
            type="MelodyLoops",
            duration=0.0,
            analysis_warnings=["worker_crash"],
            needs_review=True,
            review_reasons=["worker_crash"],
            error="worker_crash",
        )

        update_analysis_summary(summary, result)

        self.assertEqual(summary.errors, 1)
        self.assertEqual(summary.worker_crashes, 1)
        self.assertEqual(summary.error_examples[0]["name"], "broken.wav")
        self.assertEqual(summary.crash_signature_counts[normalize_crash_signature(result)], 1)

    def test_normalize_crash_signature_uses_error_head_profile_and_engines(self) -> None:
        result = AnalysisResult(
            file_path="/samples/broken.wav",
            root_note=None,
            key=None,
            confidence=0.0,
            category="Loops",
            type="MelodyLoops",
            duration=0.0,
            analysis_profile="balanced",
            analysis_engines=["librosa", "essentia"],
            analysis_warnings=["worker_crash"],
            needs_review=True,
            review_reasons=["worker_crash"],
            error="ValueError: native decode exploded",
        )

        signature = normalize_crash_signature(result)

        self.assertEqual(
            signature,
            "ValueError | warnings=worker_crash | review=worker_crash | profile=balanced | engines=librosa,essentia",
        )

    def test_analyze_file_isolated_returns_worker_crash_result_when_pool_breaks(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.wav"
            path.write_bytes(b"audio")

            with patch("sample_key_indexer.cli.ProcessPoolExecutor") as executor_cls:
                executor = executor_cls.return_value.__enter__.return_value
                executor.submit.return_value.result.side_effect = BrokenProcessPool("boom")

                result = analyze_file_isolated(path, 30.0, 22050, "balanced", ("librosa", "essentia"))

        self.assertTrue(result.needs_review)
        self.assertEqual(result.error, "worker_crash")

    def test_print_copy_report_includes_probe_reasons_and_explained_delta(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ignored = root / "fullmix.wav"
            ignored.write_bytes(b"1234")
            long_file = root / "song.wav"
            long_file.write_bytes(b"123456")
            unsupported_summary = {".mid": type("Summary", (), {"count": 2, "bytes": 500})()}
            probe_summary = ProbeRunSummary(
                ffprobe=2,
                soundfile=0,
                librosa=0,
                unknown=1,
                failed=1,
                failed_reason_counts={"decode failed": 1},
                failed_examples=[{"backend": "python", "reason": "decode failed", "path": "unknown.wav", "raw_error": "decode failed"}],
            )
            out = StringIO()
            with redirect_stdout(out):
                print_copy_report(
                    10,
                    [],
                    [ignored],
                    [long_file],
                    unsupported_summary,
                    AnalysisRunSummary(),
                    probe_summary,
                )
            text = out.getvalue()

        self.assertIn("Failed probe reasons:", text)
        self.assertIn("decode failed: 1", text)
        self.assertIn("Failed probe examples:", text)
        self.assertIn("Explained source/output delta from skipped files:", text)

    def test_write_run_report_emits_json_with_summary_and_examples(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "output"
            input_root.mkdir()
            output_root.mkdir()
            report_path = output_root / "analysis_run_report.json"
            skipped = input_root / "fullmix.wav"
            skipped.write_bytes(b"1234")
            long_file = input_root / "song.wav"
            long_file.write_bytes(b"123456")
            summary = AnalysisRunSummary(
                errors=1,
                needs_review=2,
                low_confidence=1,
                key_disagreements=1,
                decoder_fallbacks=1,
                tiny_audio=1,
                warning_records=1,
                worker_crashes=1,
                isolated_retry_triggered=True,
                isolated_retry_files=5,
                error_examples=[{"name": "broken.wav"}],
                warning_examples=[{"name": "warn.wav"}],
                review_examples=[{"name": "review.wav"}],
            )
            probe_summary = ProbeRunSummary(ffprobe=10, soundfile=1, librosa=0, unknown=0, failed=0)

            write_run_report(
                report_path,
                processed=42,
                input_root=input_root,
                output_root=output_root,
                library_id="usb_01",
                library_name="USB 01",
                selected_engines=("librosa", "essentia"),
                analysis_profile="balanced",
                skipped_ignored=[skipped],
                skipped_long=[long_file],
                already_indexed=[],
                unsupported_by_type={".mid": FileTypeSummary(count=3, bytes=12)},
                analysis_summary=summary,
                probe_summary=probe_summary,
            )

            payload = report_path.read_text(encoding="utf-8")

        self.assertIn('"processed": 42', payload)
        self.assertIn('"isolated_retry_triggered": true', payload)
        self.assertIn('"worker_crashes": 1', payload)
        self.assertIn('"errors"', payload)
        self.assertIn('"broken.wav"', payload)
        self.assertIn('"crash_signatures"', payload)
        self.assertIn('"suspicious_files"', payload)
        self.assertIn('"explained_source_output_delta_bytes"', payload)


if __name__ == "__main__":
    unittest.main()
