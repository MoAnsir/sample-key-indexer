from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sample_key_indexer.classify import classify_sample
from sample_key_indexer.models import AnalysisResult
from sample_key_indexer.routing import destination_for


class ClassificationAndRoutingTests(unittest.TestCase):
    def test_kick_oneshot_classifies_under_drums(self) -> None:
        category, sample_type = classify_sample(Path("Hard Kick 01.wav"), 0.7)
        self.assertEqual(category, "OneShots")
        self.assertEqual(sample_type, "Kick")

    def test_bass_loop_classifies_as_bass_loop(self) -> None:
        category, sample_type = classify_sample(Path("deep_sub_bass_128bpm_loop.wav"), 8.0)
        self.assertEqual(category, "Loops")
        self.assertEqual(sample_type, "BassLoops")

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
