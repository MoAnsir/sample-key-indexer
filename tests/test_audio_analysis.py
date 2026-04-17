from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import warnings

from sample_key_indexer.audio_analysis import _normalise_bpm, _normalise_bpm_with_reason, choose_consensus_key, detect_bpm_with_review, detect_filename_bpm, detect_filename_key, ffprobe_audio_file, probe_audio_file, summarize_warnings, tiny_audio_reason


class AudioAnalysisV2Tests(unittest.TestCase):
    def test_detect_filename_key_from_common_pack_names(self) -> None:
        self.assertEqual(detect_filename_key(Path("PL_CAP_Piano_140_C_Minor_Dry.wav")), "C_minor")
        self.assertEqual(detect_filename_key(Path("KSHMR Trumpet Loop 07 (99, Gm) - Stack.wav")), "G_minor")
        self.assertEqual(detect_filename_key(Path("KSHMR Big Kick 17 (F).wav")), "F")
        self.assertEqual(detect_filename_key(Path("Bass Loop 14 Em.wav")), "E_minor")

    def test_detect_filename_bpm_prefers_pack_tempo_over_slice_range(self) -> None:
        self.assertEqual(detect_filename_bpm(Path("PL_BGSY_Bass_49-63_140_E_Min_Wet.wav")), 140.0)
        self.assertEqual(detect_filename_bpm(Path("deep_sub_bass_128bpm_loop.wav")), 128.0)

    def test_normalise_bpm_uses_filename_tempo_for_half_time_readings(self) -> None:
        self.assertEqual(round(_normalise_bpm(69.84, expected_bpm=140), 2), 140)
        self.assertEqual(round(_normalise_bpm(143.55, expected_bpm=140), 2), 140)
        self.assertEqual(round(_normalise_bpm(234.91, expected_bpm=140), 2), 140)

    def test_normalise_bpm_snaps_near_miss_to_filename_tempo_without_review(self) -> None:
        bpm, reason = _normalise_bpm_with_reason(129.2, expected_bpm=140)

        self.assertEqual(bpm, 140)
        self.assertIsNone(reason)

    def test_normalise_bpm_flags_filename_anchor_for_suspicious_tempo(self) -> None:
        bpm, reason = _normalise_bpm_with_reason(95.7, expected_bpm=140)

        self.assertEqual(bpm, 140)
        self.assertEqual(reason, "filename_bpm_anchor")

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy is required for audio array tests")
    def test_detect_bpm_with_review_uses_onset_strength_and_feature_tempo(self) -> None:
        import numpy as np

        with patch("sample_key_indexer.audio_analysis.librosa.onset.onset_strength", return_value=np.array([0.1, 0.2, 0.3])):
            with patch("sample_key_indexer.audio_analysis.librosa.feature.tempo", return_value=np.array([69.84])):
                bpm, reason = detect_bpm_with_review(np.ones(44100), 22050, 4.0, expected_bpm=140.0)

        self.assertEqual(bpm, 140.0)
        self.assertEqual(reason, [])

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy is required for audio array tests")
    def test_detect_bpm_with_review_suppresses_filename_anchor_for_drum_types(self) -> None:
        import numpy as np

        with patch("sample_key_indexer.audio_analysis.librosa.onset.onset_strength", return_value=np.array([0.1, 0.2, 0.3])):
            with patch("sample_key_indexer.audio_analysis.librosa.feature.tempo", return_value=np.array([95.7])):
                bpm, reason = detect_bpm_with_review(
                    np.ones(44100),
                    22050,
                    4.0,
                    expected_bpm=140.0,
                    sample_type="DrumLoops",
                )

        self.assertEqual(bpm, 140.0)
        self.assertEqual(reason, [])

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
        self.assertEqual(review_reasons, ["filename_key_disagreement", "filename_key_disagreement_confident"])

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
        self.assertEqual(review_reasons, ["engine_root_disagreement", "filename_key_disagreement", "filename_key_disagreement_weak"])

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
        self.assertEqual(review_reasons, ["filename_key_disagreement", "filename_key_disagreement_confident"])

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy is required for audio array tests")
    def test_tiny_audio_reason_flags_short_or_silent_audio(self) -> None:
        import numpy as np

        self.assertEqual(tiny_audio_reason(np.zeros(1000), 22050, 0.04), "tiny_audio")
        self.assertEqual(tiny_audio_reason(np.zeros(3000), 22050, 0.2), "near_silence")
        self.assertIsNone(tiny_audio_reason(np.ones(3000) * 0.1, 22050, 0.2))

    def test_summarize_warnings_groups_known_noisy_warnings(self) -> None:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            warnings.warn("PySoundFile failed. Trying audioread instead.")
            warnings.warn("n_fft=1024 is too large for input signal of length=43")
            warnings.warn("Trying to estimate tuning from empty frequency set.")
            warnings.warn("'aifc' is deprecated and slated for removal in Python 3.13", DeprecationWarning)

        self.assertEqual(
            summarize_warnings(captured),
            ["decoder_fallback_audioread", "short_signal_fft_adjusted", "empty_frequency_set"],
        )

    def test_ffprobe_audio_file_parses_stream_duration_and_sample_rate(self) -> None:
        completed = Mock()
        completed.returncode = 0
        completed.stdout = '{"streams":[{"duration":"12.3456","sample_rate":"48000"}],"format":{"duration":"12.3456"}}'
        completed.stderr = ""

        with patch("sample_key_indexer.audio_analysis.shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("sample_key_indexer.audio_analysis.subprocess.run", return_value=completed):
                probe = ffprobe_audio_file(Path("loop.wav"))

        self.assertEqual(probe.duration, 12.346)
        self.assertEqual(probe.sample_rate, 48000)
        self.assertEqual(probe.backend, "ffprobe")

    def test_probe_audio_file_falls_back_to_python_when_ffprobe_is_missing_in_auto_mode(self) -> None:
        with patch("sample_key_indexer.audio_analysis.ffprobe_audio_file", return_value=Mock(duration=None, backend="ffprobe", error="ffprobe_not_found")):
            with patch("sample_key_indexer.audio_analysis.python_audio_file_info", return_value=Mock(duration=3.0, backend="soundfile")):
                probe = probe_audio_file(Path("kick.wav"), "auto")

        self.assertEqual(probe.duration, 3.0)
        self.assertEqual(probe.backend, "soundfile")


if __name__ == "__main__":
    unittest.main()
