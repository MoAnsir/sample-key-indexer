from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.web_app import (
    _flatten_sample,
    _playable_path,
    _with_playback_info,
    organized_relative_path,
    parse_allowed_networks,
    parse_library_roots,
    summarize_by_type,
    summarize_libraries,
)


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

    def test_summarize_libraries_counts_playback_state(self) -> None:
        libraries = summarize_libraries([
            {"library_id": "usb_01", "library_name": "USB 01", "playback_status": "available", "playback_source": "organized_mounted_root", "index_path": "/indexes/usb.sqlite"},
            {"library_id": "usb_01", "library_name": "USB 01", "playback_status": "missing", "playback_source": "missing", "index_path": "/indexes/usb.sqlite"},
            {"library_id": "sd_02", "library_name": "SD 02", "playback_status": "available", "playback_source": "source_mounted_root", "index_path": "/indexes/sd.sqlite"},
        ])

        self.assertEqual(libraries[0]["id"], "sd_02")
        self.assertEqual(libraries[0]["available"], 1)
        self.assertEqual(libraries[1]["id"], "usb_01")
        self.assertEqual(libraries[1]["total"], 2)
        self.assertEqual(libraries[1]["missing"], 1)
        self.assertEqual(libraries[1]["sources"][0], {"source": "missing", "count": 1})

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
            relative_path="Pads/pad_dark_em.wav",
            library_id="usb_01",
            library_name="USB 01",
            library_root="/Volumes/USB_01/Samples",
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
        self.assertEqual(sample["relative_path"], "Pads/pad_dark_em.wav")
        self.assertEqual(sample["library_id"], "usb_01")
        self.assertEqual(sample["library_name"], "USB 01")
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

    def test_playable_path_uses_library_root_override(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "Kicks" / "kick.wav"
            audio_path.parent.mkdir()
            audio_path.write_bytes(b"audio")

            sample = {
                "destination": "/missing/Key/C_major/OneShots/Drums/Kick/kick.wav",
                "file_path": "/old_mount/Kicks/kick.wav",
                "relative_path": "Kicks/kick.wav",
                "library_id": "usb_01",
            }

            playable_path = _playable_path(sample, {"usb_01": root})

        self.assertEqual(playable_path, str(audio_path))

    def test_playable_path_uses_destination_root_override(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "Key" / "C_major" / "OneShots" / "Drums" / "Kick" / "kick.wav"
            audio_path.parent.mkdir(parents=True)
            audio_path.write_bytes(b"audio")

            sample = {
                "destination": "/Users/mohammedansir/Desktop/SampleIndexes/usb_01/Key/C_major/OneShots/Drums/Kick/kick.wav",
                "file_path": "/missing_source/Kicks/kick.wav",
                "relative_path": "Kicks/kick.wav",
                "library_id": "usb_01",
            }

            playable_path = _playable_path(sample, destination_roots={"usb_01": root})

        self.assertEqual(playable_path, str(audio_path))

    def test_organized_relative_path_starts_at_key_or_unsorted(self) -> None:
        self.assertEqual(
            organized_relative_path("/tmp/catalog/Key/A_minor/Loops/BassLoops/bass.wav"),
            Path("Key/A_minor/Loops/BassLoops/bass.wav"),
        )
        self.assertEqual(
            organized_relative_path("/tmp/catalog/Unsorted/OneShots/FX/noise.wav"),
            Path("Unsorted/OneShots/FX/noise.wav"),
        )

    def test_playback_info_updates_when_library_root_becomes_available(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "Kicks" / "kick.wav"
            sample = {
                "destination": "/missing/Key/C_major/OneShots/Drums/Kick/kick.wav",
                "file_path": "/old_mount/Kicks/kick.wav",
                "relative_path": "Kicks/kick.wav",
                "library_id": "usb_01",
            }

            missing = _with_playback_info(sample, {"usb_01": root})
            audio_path.parent.mkdir()
            audio_path.write_bytes(b"audio")
            available = _with_playback_info(sample, {"usb_01": root})

        self.assertEqual(missing["playback_status"], "missing")
        self.assertEqual(missing["playback_source"], "missing")
        self.assertEqual(available["playback_status"], "available")
        self.assertEqual(available["playback_source"], "source_mounted_root")
        self.assertEqual(available["playable_path"], str(audio_path))

    def test_parse_library_roots_requires_library_id(self) -> None:
        with self.assertRaises(ValueError):
            parse_library_roots(["/Volumes/USB_01/Samples"])

    def test_parse_destination_roots_uses_option_name_in_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "--destination-root"):
            parse_library_roots(["/Volumes/USB_01/SAMPLEZ"], option_name="--destination-root")

    def test_parse_allowed_networks_accepts_ips_and_cidrs(self) -> None:
        allowed = parse_allowed_networks(["192.168.1.10", "2001:db8::1"], ["10.0.0.0/8", "2001:db8::/32"])
        self.assertEqual(len(allowed), 4)

    def test_parse_allowed_networks_rejects_bad_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid --allow-ip"):
            parse_allowed_networks(["not-an-ip"], [])
        with self.assertRaisesRegex(ValueError, "Invalid --allow-cidr"):
            parse_allowed_networks([], ["not-a-cidr"])


if __name__ == "__main__":
    unittest.main()
