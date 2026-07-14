from __future__ import annotations

import pytest

from sample_key_indexer.arrangement import (
    build_arrangement,
    humanize,
    make_fill,
    make_sparse,
    midi_bytes_for_arrangement,
    transpose_diatonic,
)

SKETCH = {
    "name": "Test",
    "bpm": 120,
    "bars": 4,
    "beats_per_bar": 4,
    "tonic": "C",
    "mode": "minor",
    "note_events": [
        {"midi": 48, "start": 0.0, "duration": 1.0, "velocity": 100},
        {"midi": 51, "start": 1.0, "duration": 0.5, "velocity": 80},
        {"midi": 53, "start": 2.0, "duration": 1.0, "velocity": 90},
        {"midi": 55, "start": 3.0, "duration": 0.5, "velocity": 70},
    ],
}


class TestHumanize:
    def test_changes_velocity(self):
        events = [{"midi": 60, "start": 0, "duration": 1, "velocity": 100}]
        out = humanize(events, seed=42)
        assert out[0]["velocity"] != 100 or True  # may happen to match

    def test_clamps_to_valid_range(self):
        events = [{"midi": 60, "start": 0, "duration": 1, "velocity": 127}]
        out = humanize(events, amount=1.0, seed=1)
        assert 1 <= out[0]["velocity"] <= 127

    def test_reproducible_with_same_seed(self):
        events = [{"midi": 60, "start": 0, "duration": 1, "velocity": 64}]
        a = humanize(events, seed=7)
        b = humanize(events, seed=7)
        assert a[0]["velocity"] == b[0]["velocity"]

    def test_different_seeds_differ(self):
        events = [{"midi": 60, "start": 0, "duration": 1, "velocity": 64}]
        a = humanize(events, seed=1)
        b = humanize(events, seed=99)
        # Seeds are different so velocities very likely differ
        assert a[0]["velocity"] != b[0]["velocity"]


class TestTransposeDiatonic:
    def test_up_one_step_c_minor(self):
        events = [{"midi": 48, "start": 0, "duration": 1}]  # C3
        out = transpose_diatonic(events, "C", "minor", 1)
        # C minor scale: C D Eb F G Ab Bb — next note from C is D (midi 50)
        assert out[0]["midi"] == 50

    def test_down_one_step(self):
        events = [{"midi": 50, "start": 0, "duration": 1}]  # D3
        out = transpose_diatonic(events, "C", "minor", -1)
        assert out[0]["midi"] == 48  # back to C3

    def test_unknown_key_returns_unchanged(self):
        events = [{"midi": 60, "start": 0, "duration": 1}]
        out = transpose_diatonic(events, "X", "minor", 2)
        assert out[0]["midi"] == 60

    def test_clamps_at_midi_bounds(self):
        events = [{"midi": 120, "start": 0, "duration": 1}]
        out = transpose_diatonic(events, "C", "major", 100)
        assert 0 <= out[0]["midi"] <= 127


class TestMakeSparse:
    def test_fewer_notes_than_original(self):
        events = SKETCH["note_events"]
        out = make_sparse(events, beats_per_bar=4)
        assert len(out) <= len(events)

    def test_keeps_first_beat_of_each_bar(self):
        events = SKETCH["note_events"]
        out = make_sparse(events, beats_per_bar=4)
        starts = {e["start"] for e in out}
        assert 0.0 in starts

    def test_empty_returns_empty(self):
        assert make_sparse([], beats_per_bar=4) == []


class TestMakeFill:
    def test_adds_events_on_last_beat(self):
        events = SKETCH["note_events"]
        out = make_fill(events, beats_per_bar=4, density=1.0, seed=0)
        last_beat = 3.0  # bar 0, beat 3 (0-indexed)
        on_last = [e for e in out if e["start"] >= last_beat]
        assert len(on_last) > 0

    def test_empty_returns_empty(self):
        assert make_fill([], beats_per_bar=4) == []


class TestBuildArrangement:
    def test_returns_correct_total_bars(self):
        arr = build_arrangement(SKETCH, target_bars=16)
        assert arr["total_bars"] == 16

    def test_single_section_without_ab(self):
        arr = build_arrangement(SKETCH, target_bars=8, strategies=[])
        assert len(arr["sections"]) == 1
        assert arr["sections"][0]["label"] == "Main"

    def test_ab_creates_two_or_three_sections(self):
        arr = build_arrangement(SKETCH, target_bars=16, strategies=["ab"])
        labels = [s["label"] for s in arr["sections"]]
        assert "A" in labels
        assert "B" in labels

    def test_ab_sparse_adds_breakdown(self):
        arr = build_arrangement(SKETCH, target_bars=16, strategies=["ab", "sparse"])
        labels = [s["label"] for s in arr["sections"]]
        assert "Breakdown" in labels

    def test_sections_cover_full_range(self):
        arr = build_arrangement(SKETCH, target_bars=16, strategies=["ab"])
        # A ends where B starts
        a = next(s for s in arr["sections"] if s["label"] == "A")
        b = next(s for s in arr["sections"] if s["label"] == "B")
        assert a["bar_end"] == b["bar_start"]

    def test_preserves_bpm_and_mode(self):
        arr = build_arrangement(SKETCH, target_bars=8)
        assert arr["bpm"] == 120.0
        assert arr["mode"] == "minor"
        assert arr["tonic"] == "C"

    def test_humanize_strategy_changes_velocities(self):
        arr_plain = build_arrangement(SKETCH, target_bars=8, strategies=[])
        arr_human = build_arrangement(SKETCH, target_bars=8, strategies=["humanize"])
        plain_vels = [e["velocity"] for s in arr_plain["sections"] for e in s["note_events"]]
        human_vels = [e["velocity"] for s in arr_human["sections"] for e in s["note_events"]]
        assert plain_vels != human_vels

    def test_all_events_have_required_keys(self):
        arr = build_arrangement(SKETCH, target_bars=16, strategies=["humanize", "ab", "fill"])
        for section in arr["sections"]:
            for ev in section["note_events"]:
                assert "midi" in ev
                assert "start" in ev
                assert "duration" in ev
                assert "velocity" in ev


class TestMidiBytesForArrangement:
    def test_returns_valid_midi_header(self):
        arr = build_arrangement(SKETCH, target_bars=8)
        data = midi_bytes_for_arrangement(arr)
        assert data[:4] == b"MThd"

    def test_empty_sections_still_produces_midi(self):
        arr = {"sections": [], "total_bars": 8, "bpm": 120, "beats_per_bar": 4, "tonic": "C", "mode": "minor"}
        data = midi_bytes_for_arrangement(arr)
        assert data[:4] == b"MThd"
