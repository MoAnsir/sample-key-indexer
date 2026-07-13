from __future__ import annotations

import unittest

import io

from sample_key_indexer.sketch import (
    analyze_sketch,
    midi_bytes_for_sketch,
    note_token_to_midi,
    out_of_scale_notes,
    parse_note_name,
    sketch_to_sample,
    validate_sketch_payload,
)


def base_payload(**overrides):
    payload = {
        "name": "MPC bass idea",
        "tonic": "Eb",
        "mode": "minor",
        "bpm": 140,
        "bars": 8,
        "type": "Bass",
    }
    payload.update(overrides)
    return payload


class ParseNoteNameTests(unittest.TestCase):
    def test_parses_flats_to_sharps(self) -> None:
        self.assertEqual(parse_note_name("Eb"), "D#")
        self.assertEqual(parse_note_name("Bb"), "A#")

    def test_parses_naturals_and_sharps(self) -> None:
        self.assertEqual(parse_note_name("A"), "A")
        self.assertEqual(parse_note_name("F#"), "F#")

    def test_strips_octave_suffix(self) -> None:
        self.assertEqual(parse_note_name("Eb2"), "D#")
        self.assertEqual(parse_note_name("C-1"), "C")

    def test_parses_lowercase(self) -> None:
        self.assertEqual(parse_note_name("eb"), "D#")
        self.assertEqual(parse_note_name("g#3"), "G#")

    def test_parses_midi_numbers(self) -> None:
        self.assertEqual(parse_note_name(60), "C")
        self.assertEqual(parse_note_name(38), "D")

    def test_rejects_invalid(self) -> None:
        self.assertIsNone(parse_note_name("H"))
        self.assertIsNone(parse_note_name("Xb"))
        self.assertIsNone(parse_note_name(""))
        self.assertIsNone(parse_note_name(None))
        self.assertIsNone(parse_note_name(200))
        self.assertIsNone(parse_note_name(True))


class NoteTokenToMidiTests(unittest.TestCase):
    def test_note_with_octave(self) -> None:
        self.assertEqual(note_token_to_midi("C4"), 60)
        self.assertEqual(note_token_to_midi("Eb2"), 39)

    def test_bare_pitch_class_uses_default_octave(self) -> None:
        self.assertEqual(note_token_to_midi("C"), 36)  # C2
        self.assertEqual(note_token_to_midi("C", default_octave=4), 60)

    def test_passes_through_midi_numbers(self) -> None:
        self.assertEqual(note_token_to_midi(38), 38)

    def test_rejects_out_of_range(self) -> None:
        self.assertIsNone(note_token_to_midi(128))
        self.assertIsNone(note_token_to_midi(-1))
        self.assertIsNone(note_token_to_midi("C99"))


class ValidateSketchPayloadTests(unittest.TestCase):
    def test_valid_minimal_payload(self) -> None:
        sketch, errors = validate_sketch_payload(base_payload())
        self.assertEqual(errors, [])
        self.assertEqual(sketch["tonic"], "D#")
        self.assertEqual(sketch["mode"], "minor")
        self.assertEqual(sketch["bpm"], 140)
        self.assertEqual(sketch["bars"], 8)
        self.assertEqual(sketch["beats_per_bar"], 4)
        self.assertEqual(sketch["type"], "Bass")
        self.assertEqual(sketch["name"], "MPC bass idea")

    def test_defaults_name_when_missing(self) -> None:
        sketch, _ = validate_sketch_payload(base_payload(name=""))
        self.assertEqual(sketch["name"], "Untitled Sketch")

    def test_accepts_root_note_alias(self) -> None:
        payload = base_payload()
        payload.pop("tonic")
        payload["root_note"] = "Eb"
        sketch, errors = validate_sketch_payload(payload)
        self.assertEqual(errors, [])
        self.assertEqual(sketch["tonic"], "D#")

    def test_rejects_missing_tonic(self) -> None:
        payload = base_payload()
        payload.pop("tonic")
        sketch, errors = validate_sketch_payload(payload)
        self.assertIsNone(sketch)
        self.assertTrue(any("tonic" in e for e in errors))

    def test_rejects_bad_mode(self) -> None:
        _, errors = validate_sketch_payload(base_payload(mode="dorian"))
        self.assertTrue(any("mode" in e for e in errors))

    def test_rejects_bad_bpm(self) -> None:
        _, errors = validate_sketch_payload(base_payload(bpm=1000))
        self.assertTrue(any("bpm" in e for e in errors))
        _, errors = validate_sketch_payload(base_payload(bpm="fast"))
        self.assertTrue(any("bpm" in e for e in errors))

    def test_rejects_bad_bars(self) -> None:
        _, errors = validate_sketch_payload(base_payload(bars=0))
        self.assertTrue(any("bars" in e for e in errors))

    def test_rejects_unknown_type(self) -> None:
        _, errors = validate_sketch_payload(base_payload(type="Sub"))
        self.assertTrue(any("type" in e for e in errors))

    def test_rejects_unknown_frequency_register(self) -> None:
        _, errors = validate_sketch_payload(base_payload(frequency_register="ultra"))
        self.assertTrue(any("frequency_register" in e for e in errors))

    def test_accepts_valid_frequency_register(self) -> None:
        sketch, errors = validate_sketch_payload(base_payload(frequency_register="sub"))
        self.assertEqual(errors, [])
        self.assertEqual(sketch["frequency_register"], "sub")

    def test_normalizes_quick_notes(self) -> None:
        sketch, errors = validate_sketch_payload(
            base_payload(notes=["Eb", "Gb", "Bb", "Eb"])
        )
        self.assertEqual(errors, [])
        self.assertEqual(sketch["notes"], ["D#", "F#", "A#"])  # deduped, flats normalized

    def test_rejects_invalid_note_token(self) -> None:
        _, errors = validate_sketch_payload(base_payload(notes=["Eb", "Zz"]))
        self.assertTrue(any("invalid note" in e for e in errors))

    def test_accepts_note_events(self) -> None:
        events = [
            {"note": "Eb2", "start": 0.0, "duration": 1.0, "velocity": 100},
            {"note": "Gb2", "start": 1.0, "duration": 0.5, "velocity": 90},
        ]
        sketch, errors = validate_sketch_payload(base_payload(note_events=events))
        self.assertEqual(errors, [])
        self.assertEqual(len(sketch["note_events"]), 2)
        self.assertEqual(sketch["note_events"][0]["midi"], 39)
        self.assertEqual(sketch["note_events"][0]["note"], "D#")

    def test_clamps_velocity(self) -> None:
        events = [{"note": "C2", "start": 0, "duration": 1, "velocity": 300}]
        sketch, _ = validate_sketch_payload(base_payload(note_events=events))
        self.assertEqual(sketch["note_events"][0]["velocity"], 127)

    def test_rejects_negative_start_or_zero_duration(self) -> None:
        events = [{"note": "C2", "start": -1, "duration": 1}]
        _, errors = validate_sketch_payload(base_payload(note_events=events))
        self.assertTrue(any("start/duration" in e for e in errors))
        events = [{"note": "C2", "start": 0, "duration": 0}]
        _, errors = validate_sketch_payload(base_payload(note_events=events))
        self.assertTrue(any("start/duration" in e for e in errors))

    def test_rejects_invalid_event_note(self) -> None:
        events = [{"note": "Zz", "start": 0, "duration": 1}]
        _, errors = validate_sketch_payload(base_payload(note_events=events))
        self.assertTrue(any(".note is invalid" in e for e in errors))


class SketchToSampleTests(unittest.TestCase):
    def _sketch(self, **overrides):
        sketch, errors = validate_sketch_payload(base_payload(**overrides))
        assert errors == [], errors
        return sketch

    def test_builds_key_and_root(self) -> None:
        sample = sketch_to_sample(self._sketch())
        self.assertEqual(sample["key"], "D#_minor")
        self.assertEqual(sample["root_note"], "D#")
        self.assertEqual(sample["source_kind"], "sketch")

    def test_uses_scale_notes_when_none_played(self) -> None:
        sample = sketch_to_sample(self._sketch())
        self.assertIn("D#", sample["notes"])
        self.assertEqual(len(sample["notes"]), 7)  # full minor scale

    def test_uses_played_notes_when_given(self) -> None:
        sample = sketch_to_sample(self._sketch(notes=["Eb", "Gb"]))
        self.assertEqual(sample["notes"], ["D#", "F#"])

    def test_collects_notes_from_events(self) -> None:
        events = [
            {"note": "Eb2", "start": 0, "duration": 1},
            {"note": "Bb2", "start": 1, "duration": 1},
        ]
        sample = sketch_to_sample(self._sketch(note_events=events))
        self.assertEqual(sample["notes"], ["D#", "A#"])

    def test_duration_from_bars_and_bpm(self) -> None:
        # 8 bars * 4 beats = 32 beats at 140bpm -> 32 * 60/140 ≈ 13.714s
        sample = sketch_to_sample(self._sketch())
        self.assertAlmostEqual(sample["duration"], 13.714, places=3)

    def test_loop_types_get_loops_category(self) -> None:
        sample = sketch_to_sample(self._sketch(type="BassLoops"))
        self.assertEqual(sample["category"], "Loops")
        sample = sketch_to_sample(self._sketch(type="Bass"))
        self.assertEqual(sample["category"], "OneShots")


class OutOfScaleNotesTests(unittest.TestCase):
    def test_flags_notes_outside_scale(self) -> None:
        sketch, _ = validate_sketch_payload(base_payload(notes=["Eb", "E"]))
        # E natural is not in Eb minor
        self.assertEqual(out_of_scale_notes(sketch), ["E"])

    def test_empty_when_all_in_scale(self) -> None:
        sketch, _ = validate_sketch_payload(base_payload(notes=["Eb", "Gb", "Bb"]))
        self.assertEqual(out_of_scale_notes(sketch), [])


class AnalyzeSketchTests(unittest.TestCase):
    def test_returns_errors_for_invalid_payload(self) -> None:
        result, errors = analyze_sketch({})
        self.assertIsNone(result)
        self.assertTrue(errors)

    def test_full_analysis_shape(self) -> None:
        result, errors = analyze_sketch(base_payload(notes=["Eb", "Gb", "Bb"]))
        self.assertEqual(errors, [])
        self.assertIn("sketch", result)
        self.assertIn("sample", result)
        self.assertIn("context", result)
        context = result["context"]
        self.assertEqual(context["musical_record"]["key"], "D#_minor")
        self.assertEqual(context["musical_record"]["bpm"], 140)
        self.assertTrue(context["compatibility"]["keys"])
        self.assertTrue(context["compatibility"]["progressions"])
        self.assertIn("primary", context["mood_profile"])
        self.assertTrue(context["transition_suggestions"])

    def test_mood_reflects_minor_fast(self) -> None:
        result, _ = analyze_sketch(base_payload())
        # minor mode at 140bpm should read as dark
        self.assertEqual(result["context"]["mood_profile"]["primary"], "dark")

    def test_compat_keys_include_relative_major(self) -> None:
        result, _ = analyze_sketch(base_payload())
        labels = {k["label"]: k["key"] for k in result["context"]["compatibility"]["keys"]}
        # relative major of Eb minor is Gb major (F# major normalized)
        self.assertEqual(labels["Relative key"], "F#_major")

    def test_out_of_scale_reported(self) -> None:
        result, _ = analyze_sketch(base_payload(notes=["Eb", "E"]))
        self.assertEqual(result["out_of_scale_notes"], ["E"])


class MidiBytesForSketchTests(unittest.TestCase):
    def _sketch(self, **overrides):
        sketch, errors = validate_sketch_payload(base_payload(**overrides))
        assert errors == [], errors
        return sketch

    def _events(self):
        return [
            {"note": "Eb2", "start": 0.0, "duration": 1.0, "velocity": 100},
            {"note": "Gb2", "start": 1.0, "duration": 0.5, "velocity": 90},
            {"note": "Bb2", "start": 2.0, "duration": 2.0, "velocity": 110},
        ]

    def test_raises_without_note_events(self) -> None:
        with self.assertRaises(ValueError):
            midi_bytes_for_sketch(self._sketch())

    def test_produces_valid_midi_bytes(self) -> None:
        body = midi_bytes_for_sketch(self._sketch(note_events=self._events()))
        self.assertTrue(body.startswith(b"MThd"))  # standard MIDI header

    def test_notes_round_trip(self) -> None:
        import pretty_midi

        body = midi_bytes_for_sketch(self._sketch(note_events=self._events()))
        midi = pretty_midi.PrettyMIDI(io.BytesIO(body))
        self.assertEqual(len(midi.instruments), 1)
        notes = sorted(midi.instruments[0].notes, key=lambda n: n.start)
        self.assertEqual(len(notes), 3)
        # pitches: Eb2=39, Gb2=42, Bb2=46
        self.assertEqual([n.pitch for n in notes], [39, 42, 46])
        self.assertEqual([n.velocity for n in notes], [100, 90, 110])

    def test_timing_uses_bpm(self) -> None:
        import pretty_midi

        # 140 bpm -> one beat = 60/140 ≈ 0.4286s
        body = midi_bytes_for_sketch(self._sketch(note_events=self._events()))
        midi = pretty_midi.PrettyMIDI(io.BytesIO(body))
        notes = sorted(midi.instruments[0].notes, key=lambda n: n.start)
        beat = 60.0 / 140.0
        self.assertAlmostEqual(notes[0].start, 0.0, places=3)
        self.assertAlmostEqual(notes[0].end, beat, places=3)
        self.assertAlmostEqual(notes[1].start, beat, places=3)
        self.assertAlmostEqual(notes[1].end, beat * 1.5, places=3)
        self.assertAlmostEqual(notes[2].start, beat * 2, places=3)
        self.assertAlmostEqual(notes[2].end, beat * 4, places=3)

    def test_tempo_embedded(self) -> None:
        import pretty_midi

        body = midi_bytes_for_sketch(self._sketch(note_events=self._events()))
        midi = pretty_midi.PrettyMIDI(io.BytesIO(body))
        _, tempi = midi.get_tempo_changes()
        self.assertAlmostEqual(tempi[0], 140.0, places=1)

    def test_time_signature_embedded(self) -> None:
        import pretty_midi

        body = midi_bytes_for_sketch(
            self._sketch(beats_per_bar=3, note_events=self._events())
        )
        midi = pretty_midi.PrettyMIDI(io.BytesIO(body))
        self.assertEqual(midi.time_signature_changes[0].numerator, 3)
        self.assertEqual(midi.time_signature_changes[0].denominator, 4)

    def test_instrument_named_after_sketch(self) -> None:
        import pretty_midi

        body = midi_bytes_for_sketch(self._sketch(note_events=self._events()))
        midi = pretty_midi.PrettyMIDI(io.BytesIO(body))
        self.assertEqual(midi.instruments[0].name, "MPC bass idea")


if __name__ == "__main__":
    unittest.main()
