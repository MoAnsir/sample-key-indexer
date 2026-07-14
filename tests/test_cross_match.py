from __future__ import annotations

import pytest

from sample_key_indexer.cross_match import (
    cross_match,
    score_bpm,
    score_freq,
    score_key,
    score_mood,
    score_sample,
)

SKETCH_C_MINOR = {
    "tonic": "C",
    "mode": "minor",
    "bpm": 120,
    "frequency_register": "low",
}

SAMPLE_C_MINOR = {
    "id": 1,
    "name": "bass_loop.wav",
    "key": "C_minor",
    "bpm": 120,
    "type": "Bass",
    "brightness": "dark",
    "warmth": "warm",
    "source_kind": "audio",
}

SAMPLE_EB_MAJOR = {
    "id": 2,
    "name": "pad_Eb.wav",
    "key": "D#_major",  # stored as sharp; Eb relative of C minor
    "bpm": 90,
    "type": "Pads",
    "brightness": "bright",
    "warmth": "neutral",
    "source_kind": "audio",
}

SAMPLE_UNRELATED = {
    "id": 3,
    "name": "fx_noise.wav",
    "key": "F#_major",
    "bpm": 175,
    "type": "FX",
    "brightness": "bright",
    "warmth": "dry",
    "source_kind": "audio",
}


class TestScoreKey:
    def test_same_key_full_weight(self):
        score, reasons = score_key(SAMPLE_C_MINOR, SKETCH_C_MINOR)
        assert score == pytest.approx(0.4)
        assert "same key" in reasons

    def test_relative_key_partial_weight(self):
        # Eb major is the relative major of C minor
        score, reasons = score_key(SAMPLE_EB_MAJOR, SKETCH_C_MINOR)
        assert score == pytest.approx(0.4 * 0.7)
        assert "relative key" in reasons

    def test_no_match_returns_zero(self):
        score, reasons = score_key(SAMPLE_UNRELATED, SKETCH_C_MINOR)
        assert score == 0.0
        assert reasons == []

    def test_missing_sample_key_returns_zero(self):
        score, _ = score_key({**SAMPLE_C_MINOR, "key": None}, SKETCH_C_MINOR)
        assert score == 0.0

    def test_missing_sketch_tonic_returns_zero(self):
        score, _ = score_key(SAMPLE_C_MINOR, {**SKETCH_C_MINOR, "tonic": None})
        assert score == 0.0


class TestScoreFreq:
    def test_bass_sample_matches_low_sketch(self):
        score, reasons = score_freq(SAMPLE_C_MINOR, SKETCH_C_MINOR)
        assert score == pytest.approx(0.25)
        assert any("low" in r for r in reasons)

    def test_no_register_returns_zero(self):
        score, _ = score_freq(SAMPLE_C_MINOR, {**SKETCH_C_MINOR, "frequency_register": None})
        assert score == 0.0

    def test_unrelated_type_returns_zero(self):
        score, _ = score_freq({**SAMPLE_C_MINOR, "type": "Tops"}, SKETCH_C_MINOR)
        assert score == 0.0

    def test_pad_complements_mid_sketch(self):
        score, _ = score_freq(SAMPLE_EB_MAJOR, {**SKETCH_C_MINOR, "frequency_register": "mid"})
        assert score == pytest.approx(0.25)


class TestScoreMood:
    def test_warm_dark_matches_minor(self):
        score, reasons = score_mood(SAMPLE_C_MINOR, SKETCH_C_MINOR)
        assert score > 0
        assert len(reasons) >= 1

    def test_no_brightness_returns_zero(self):
        score, _ = score_mood({**SAMPLE_C_MINOR, "brightness": None, "warmth": None}, SKETCH_C_MINOR)
        assert score == 0.0


class TestScoreBpm:
    def test_exact_bpm_full_weight(self):
        score, reasons = score_bpm(SAMPLE_C_MINOR, SKETCH_C_MINOR)
        assert score == pytest.approx(0.15)
        assert "same BPM" in reasons

    def test_halftime_match(self):
        score, reasons = score_bpm({**SAMPLE_C_MINOR, "bpm": 60}, SKETCH_C_MINOR)
        assert score > 0
        assert any("halftime" in r for r in reasons)

    def test_doubletime_match(self):
        score, reasons = score_bpm({**SAMPLE_C_MINOR, "bpm": 240}, SKETCH_C_MINOR)
        assert score > 0
        assert any("doubletime" in r for r in reasons)

    def test_far_bpm_returns_zero(self):
        score, _ = score_bpm({**SAMPLE_C_MINOR, "bpm": 175}, SKETCH_C_MINOR)
        assert score == 0.0

    def test_zero_bpm_returns_zero(self):
        score, _ = score_bpm({**SAMPLE_C_MINOR, "bpm": 0}, SKETCH_C_MINOR)
        assert score == 0.0


class TestScoreSample:
    def test_composite_positive_score(self):
        score, reasons = score_sample(SAMPLE_C_MINOR, SKETCH_C_MINOR)
        assert score > 0
        assert len(reasons) > 0

    def test_disable_key_filter(self):
        score_all, _ = score_sample(SAMPLE_C_MINOR, SKETCH_C_MINOR)
        score_no_key, _ = score_sample(SAMPLE_C_MINOR, SKETCH_C_MINOR, {"key_compat": False, "freq_slot": True, "mood": True, "bpm": True})
        assert score_no_key < score_all

    def test_score_capped_at_one(self):
        score, _ = score_sample(SAMPLE_C_MINOR, SKETCH_C_MINOR)
        assert score <= 1.0


class TestCrossMatch:
    def test_returns_top_n(self):
        samples = [SAMPLE_C_MINOR, SAMPLE_EB_MAJOR, SAMPLE_UNRELATED]
        results = cross_match(SKETCH_C_MINOR, samples, top_n=2)
        assert len(results) <= 2

    def test_sorted_descending_by_score(self):
        samples = [SAMPLE_C_MINOR, SAMPLE_EB_MAJOR, SAMPLE_UNRELATED]
        results = cross_match(SKETCH_C_MINOR, samples)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_sketch_entries_excluded(self):
        sketch_sample = {**SAMPLE_C_MINOR, "source_kind": "sketch"}
        results = cross_match(SKETCH_C_MINOR, [sketch_sample, SAMPLE_EB_MAJOR])
        ids = [r["id"] for r in results]
        assert sketch_sample["id"] not in ids

    def test_results_have_score_and_reasons(self):
        results = cross_match(SKETCH_C_MINOR, [SAMPLE_C_MINOR])
        assert "score" in results[0]
        assert "match_reasons" in results[0]

    def test_zero_scoring_samples_excluded(self):
        # A sample with no key/bpm/brightness that can match scores 0 and is excluded
        bare = {"id": 99, "name": "x.wav", "key": None, "bpm": None, "type": None,
                "brightness": None, "warmth": None, "source_kind": "audio"}
        results = cross_match(SKETCH_C_MINOR, [bare])
        assert all(r["id"] != 99 for r in results)
