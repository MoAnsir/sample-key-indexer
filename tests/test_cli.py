from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sample_key_indexer.audio_analysis import AudioProbe
from sample_key_indexer.cli import AnalysisRunSummary, attach_library_metadata, format_gb, missing_required_external_tools, slugify, split_ignored_files, summarize_paths_by_extension, summarize_unsupported_files, split_long_files, update_analysis_summary
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
            Path("Loops/drum_loop_128.wav"),
        ]

        processable, skipped = split_ignored_files(paths)

        self.assertEqual(processable, [Path("Loops/drum_loop_128.wav")])
        self.assertEqual(skipped, [Path("Loops/PL_pack_FullMix_128_C.wav"), Path("Loops/PL pack full mix master.wav")])

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


if __name__ == "__main__":
    unittest.main()
