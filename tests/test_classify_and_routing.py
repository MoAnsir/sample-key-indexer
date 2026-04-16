from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sample_key_indexer.classify import classify_sample
from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.routing import destination_for


class FakeAudio:
    size = 2048


class ClassificationAndRoutingTests(unittest.TestCase):
    def test_kick_oneshot_classifies_under_drums(self) -> None:
        category, sample_type = classify_sample(Path("Hard Kick 01.wav"), 0.7)
        self.assertEqual(category, "OneShots")
        self.assertEqual(sample_type, "Kick")

    def test_bass_loop_classifies_as_bass_loop(self) -> None:
        category, sample_type = classify_sample(Path("deep_sub_bass_128bpm_loop.wav"), 8.0)
        self.assertEqual(category, "Loops")
        self.assertEqual(sample_type, "BassLoops")

    def test_filename_hat_beats_misleading_kick_folder(self) -> None:
        category, sample_type = classify_sample(Path("Kicks/HH_Open_01.wav"), 0.4)
        self.assertEqual(category, "OneShots")
        self.assertEqual(sample_type, "Hat")

    def test_drum_fill_name_routes_to_drum_loops_even_in_fx_folder(self) -> None:
        category, sample_type = classify_sample(Path("FX/Drum Fill 120bpm A.wav"), 3.0)
        self.assertEqual(category, "Loops")
        self.assertEqual(sample_type, "DrumLoops")

    def test_short_fill_name_routes_as_loop_not_lead_oneshot(self) -> None:
        category, sample_type = classify_sample(Path("Leads/snare_roll_fill_128.wav"), 1.4)
        self.assertEqual(category, "Loops")
        self.assertEqual(sample_type, "DrumLoops")

    def test_drum_beat_name_beats_misleading_melody_folder(self) -> None:
        category, sample_type = classify_sample(Path("Melodies/Drum_Beat_90.wav"), 8.0)
        self.assertEqual(category, "Loops")
        self.assertEqual(sample_type, "DrumLoops")

    def test_named_melodic_instrument_rescues_bright_fx_feature_guess(self) -> None:
        with patch("sample_key_indexer.classify._feature_type", return_value="FXLoops"):
            category, sample_type = classify_sample(
                Path("PL_BGSY_Saxophone_1_40-48_140_E_Min_Wet.wav"),
                13.7,
                y=FakeAudio(),
                sr=44100,
            )

        self.assertEqual(category, "Loops")
        self.assertEqual(sample_type, "MelodyLoops")

    def test_named_melodic_instrument_rescues_low_centroid_bass_feature_guess(self) -> None:
        with patch("sample_key_indexer.classify._feature_type", return_value="BassLoops"):
            category, sample_type = classify_sample(
                Path("PL_BGSY_Cello_2_36-43_140_E_Min_Wet.wav"),
                12.0,
                y=FakeAudio(),
                sr=44100,
            )

        self.assertEqual(category, "Loops")
        self.assertEqual(sample_type, "MelodyLoops")

    def test_destination_uses_key_first(self) -> None:
        with TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            result = AnalysisResult(
                file_path="/library/kick.wav",
                root_note="E",
                key="E_minor",
                confidence=0.2,
                category="OneShots",
                type="Kick",
                duration=0.4,
            )
            self.assertEqual(
                destination_for(result, output_root),
                output_root / "Key" / "E_minor" / "OneShots" / "Drums" / "Kick" / "kick.wav",
            )

    def test_destination_falls_back_to_unsorted_only_without_root(self) -> None:
        with TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            result = AnalysisResult(
                file_path="/library/noise.wav",
                root_note=None,
                key=None,
                confidence=0.0,
                category="Loops",
                type="FXLoops",
                duration=4.0,
            )
            self.assertEqual(
                destination_for(result, output_root),
                output_root / "Unsorted" / "Loops" / "FXLoops" / "noise.wav",
            )


if __name__ == "__main__":
    unittest.main()
