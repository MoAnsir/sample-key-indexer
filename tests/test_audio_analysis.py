from __future__ import annotations

from pathlib import Path
import unittest

from sample_key_indexer.audio_analysis import choose_consensus_key, detect_filename_key


class AudioAnalysisV2Tests(unittest.TestCase):
    def test_detect_filename_key_from_common_pack_names(self) -> None:
        self.assertEqual(detect_filename_key(Path("PL_CAP_Piano_140_C_Minor_Dry.wav")), "C_minor")
        self.assertEqual(detect_filename_key(Path("KSHMR Trumpet Loop 07 (99, Gm) - Stack.wav")), "G_minor")
        self.assertEqual(detect_filename_key(Path("KSHMR Big Kick 17 (F).wav")), "F")
        self.assertEqual(detect_filename_key(Path("Bass Loop 14 Em.wav")), "E_minor")

    def test_essentia_key_confidence_lifts_when_librosa_root_supports_it(self) -> None:
        key, root, confidence, review_reasons = choose_consensus_key(
            librosa_key=None,
            librosa_root="G",
            librosa_confidence=0.434,
            librosa_key_confidence=0.947,
            librosa_root_confidence=0.482,
            essentia_key="G_minor",
            essentia_root="G",
            essentia_confidence=0.73,
            filename_key="C_minor",
            sample_type="MelodyLoops",
        )

        self.assertEqual(key, "G_minor")
        self.assertEqual(root, "G")
        self.assertEqual(confidence, 0.839)
        self.assertEqual(review_reasons, ["filename_key_disagreement"])

    def test_percussive_samples_do_not_get_filename_review_noise(self) -> None:
        _, _, _, review_reasons = choose_consensus_key(
            librosa_key="D_minor",
            librosa_root="D",
            librosa_confidence=0.3,
            librosa_key_confidence=0.8,
            librosa_root_confidence=0.5,
            essentia_key="E_minor",
            essentia_root="E",
            essentia_confidence=0.8,
            filename_key="C_minor",
            sample_type="Kick",
        )

        self.assertEqual(review_reasons, ["engine_key_disagreement"])

    def test_essentia_only_choice_marks_librosa_root_disagreement(self) -> None:
        key, root, confidence, review_reasons = choose_consensus_key(
            librosa_key=None,
            librosa_root="F#",
            librosa_confidence=0.3,
            librosa_key_confidence=0.958,
            librosa_root_confidence=0.348,
            essentia_key="B_major",
            essentia_root="B",
            essentia_confidence=0.778,
            filename_key="E_minor",
            sample_type="MelodyLoops",
        )

        self.assertEqual(key, "B_major")
        self.assertEqual(root, "B")
        self.assertEqual(confidence, 0.661)
        self.assertEqual(review_reasons, ["engine_root_disagreement", "filename_key_disagreement"])

    def test_final_root_matches_final_key_when_engine_roots_disagree(self) -> None:
        key, root, confidence, review_reasons = choose_consensus_key(
            librosa_key="E_major",
            librosa_root="B",
            librosa_confidence=0.8,
            librosa_key_confidence=0.942,
            librosa_root_confidence=0.375,
            essentia_key="E_major",
            essentia_root="E",
            essentia_confidence=0.779,
            filename_key="E_minor",
            sample_type="BassLoops",
        )

        self.assertEqual(key, "E_major")
        self.assertEqual(root, "E")
        self.assertEqual(confidence, 0.88)
        self.assertEqual(review_reasons, ["filename_key_disagreement"])


if __name__ == "__main__":
    unittest.main()
