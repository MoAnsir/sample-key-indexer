"""Convert user-entered sketch data into analyzable sample dicts.

A "sketch" is a musical idea the user describes manually (key, BPM, notes
played on an MPC, etc.) instead of an audio file the scanner analyzed. The
sketch payload is converted into the same sample dict shape the audio
pipeline produces, so `build_musical_context()` gives sketches the exact
same key/mood/progression/transition analysis as scanned samples.
"""

from __future__ import annotations

import re
from typing import Any

from sample_key_indexer.music_theory import (
    FLAT_TO_SHARP,
    NOTE_ORDER,
    build_musical_context,
    scale_notes,
)

SKETCH_TYPES = {
    "Bass",
    "Chords",
    "Drums",
    "FX",
    "Kick",
    "Snare",
    "Hat",
    "Perc",
    "Leads",
    "Pads",
    "Plucks",
    "Vocals",
    "BassLoops",
    "DrumLoops",
    "FXLoops",
    "MelodyLoops",
    "VocalLoops",
}

FREQUENCY_REGISTERS = {"sub", "low", "mid", "high"}

MODES = {"major", "minor"}

_NOTE_WITH_OCTAVE = re.compile(r"^([A-Ga-g][#b]?)(-?\d+)?$")


def parse_note_name(value: Any) -> str | None:
    """Parse a note token ("Eb", "d#2", MIDI number 38) to a pitch class."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        midi = int(value)
        if 0 <= midi <= 127:
            return NOTE_ORDER[midi % 12]
        return None
    if not isinstance(value, str):
        return None
    match = _NOTE_WITH_OCTAVE.match(value.strip())
    if not match:
        return None
    name = match.group(1)
    name = name[0].upper() + name[1:]
    name = FLAT_TO_SHARP.get(name, name)
    return name if name in NOTE_ORDER else None


def note_token_to_midi(value: Any, default_octave: int = 2) -> int | None:
    """Convert a note token to a MIDI pitch. Bare pitch classes get default_octave."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        midi = int(value)
        return midi if 0 <= midi <= 127 else None
    if not isinstance(value, str):
        return None
    match = _NOTE_WITH_OCTAVE.match(value.strip())
    if not match:
        return None
    name = match.group(1)
    name = name[0].upper() + name[1:]
    name = FLAT_TO_SHARP.get(name, name)
    if name not in NOTE_ORDER:
        return None
    octave = int(match.group(2)) if match.group(2) is not None else default_octave
    midi = (octave + 1) * 12 + NOTE_ORDER.index(name)
    return midi if 0 <= midi <= 127 else None


def _clean_note_events(raw_events: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate note events; returns (clean_events, errors)."""
    if not isinstance(raw_events, list):
        return [], ["note_events must be a list"]
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, item in enumerate(raw_events):
        if not isinstance(item, dict):
            errors.append(f"note_events[{index}] must be an object")
            continue
        midi = note_token_to_midi(item.get("note"))
        if midi is None:
            errors.append(f"note_events[{index}].note is invalid")
            continue
        try:
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 1.0))
        except (TypeError, ValueError):
            errors.append(f"note_events[{index}] has invalid start/duration")
            continue
        if start < 0 or duration <= 0:
            errors.append(f"note_events[{index}] has invalid start/duration")
            continue
        try:
            velocity = int(item.get("velocity", 100))
        except (TypeError, ValueError):
            velocity = 100
        velocity = max(1, min(127, velocity))
        events.append(
            {
                "midi": midi,
                "note": NOTE_ORDER[midi % 12],
                "start": start,
                "duration": duration,
                "velocity": velocity,
            }
        )
    return events, errors


def validate_sketch_payload(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate and normalize a sketch payload. Returns (normalized, errors)."""
    errors: list[str] = []

    tonic = parse_note_name(payload.get("tonic") or payload.get("root_note"))
    if tonic is None:
        errors.append("tonic is required (e.g. 'Eb', 'D#', 'A')")

    mode = str(payload.get("mode") or "").strip().lower()
    if mode not in MODES:
        errors.append("mode must be 'major' or 'minor'")

    try:
        bpm = float(payload.get("bpm") or 0)
    except (TypeError, ValueError):
        bpm = 0
    if not 20 <= bpm <= 400:
        errors.append("bpm must be between 20 and 400")

    try:
        bars = int(payload.get("bars") or 0)
    except (TypeError, ValueError):
        bars = 0
    if not 1 <= bars <= 128:
        errors.append("bars must be between 1 and 128")

    try:
        beats_per_bar = int(payload.get("beats_per_bar") or 4)
    except (TypeError, ValueError):
        beats_per_bar = 4
    if not 1 <= beats_per_bar <= 12:
        errors.append("beats_per_bar must be between 1 and 12")

    sample_type = str(payload.get("type") or "").strip()
    if sample_type not in SKETCH_TYPES:
        errors.append(f"type must be one of: {', '.join(sorted(SKETCH_TYPES))}")

    frequency_register = str(payload.get("frequency_register") or "").strip().lower() or None
    if frequency_register is not None and frequency_register not in FREQUENCY_REGISTERS:
        errors.append(f"frequency_register must be one of: {', '.join(sorted(FREQUENCY_REGISTERS))}")

    notes: list[str] = []
    for token in payload.get("notes") or []:
        parsed = parse_note_name(token)
        if parsed is None:
            errors.append(f"invalid note: {token!r}")
        elif parsed not in notes:
            notes.append(parsed)

    note_events, event_errors = ([], []) if payload.get("note_events") is None else _clean_note_events(payload.get("note_events"))
    errors.extend(event_errors)

    if errors:
        return None, errors

    name = str(payload.get("name") or "").strip() or "Untitled Sketch"
    return (
        {
            "name": name,
            "tonic": tonic,
            "mode": mode,
            "bpm": bpm,
            "bars": bars,
            "beats_per_bar": beats_per_bar,
            "type": sample_type,
            "frequency_register": frequency_register,
            "notes": notes,
            "note_events": note_events,
        },
        [],
    )


def sketch_to_sample(sketch: dict[str, Any]) -> dict[str, Any]:
    """Build a sample dict (same shape the audio pipeline produces) from a sketch."""
    tonic = sketch["tonic"]
    mode = sketch["mode"]
    bpm = sketch["bpm"]

    played_notes = list(sketch.get("notes") or [])
    for event in sketch.get("note_events") or []:
        if event["note"] not in played_notes:
            played_notes.append(event["note"])
    if not played_notes:
        played_notes = scale_notes(tonic, mode)

    duration = sketch["bars"] * sketch["beats_per_bar"] * (60.0 / bpm)
    loop_types = {"BassLoops", "DrumLoops", "FXLoops", "MelodyLoops", "VocalLoops"}
    category = "Loops" if sketch["type"] in loop_types else "OneShots"

    return {
        "name": sketch["name"],
        "key": f"{tonic}_{mode}",
        "root_note": tonic,
        "notes": played_notes,
        "bpm": bpm,
        "type": sketch["type"],
        "category": category,
        "duration": round(duration, 3),
        "confidence": 1.0,  # user-declared, not detected
        "source_kind": "sketch",
        "frequency_register": sketch.get("frequency_register"),
        "bars": sketch["bars"],
        "beats_per_bar": sketch["beats_per_bar"],
        "note_events": sketch.get("note_events") or [],
    }


def out_of_scale_notes(sketch: dict[str, Any]) -> list[str]:
    """Notes the user played that fall outside the declared key's scale."""
    allowed = set(scale_notes(sketch["tonic"], sketch["mode"]))
    played: list[str] = []
    for note in sketch.get("notes") or []:
        if note not in allowed and note not in played:
            played.append(note)
    for event in sketch.get("note_events") or []:
        if event["note"] not in allowed and event["note"] not in played:
            played.append(event["note"])
    return played


def midi_bytes_for_sketch(sketch: dict[str, Any]) -> bytes:
    """Render a validated sketch's note events to a standard MIDI file.

    Note event start/duration are in beats; converted to seconds via the
    sketch BPM so the file plays back at the right tempo anywhere —
    including loaded back onto an MPC as a pattern.
    """
    try:
        import pretty_midi
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"missing_backend:{exc}") from exc

    events = sketch.get("note_events") or []
    if not events:
        raise ValueError("no_note_events")

    bpm = float(sketch.get("bpm") or 120.0)
    seconds_per_beat = 60.0 / max(1.0, bpm)

    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    ts_numerator = int(sketch.get("beats_per_bar") or 4)
    midi.time_signature_changes.append(pretty_midi.TimeSignature(ts_numerator, 4, 0.0))
    instrument = pretty_midi.Instrument(program=0, name=str(sketch.get("name") or "Sketch"))
    for event in events:
        start = float(event["start"]) * seconds_per_beat
        end = start + float(event["duration"]) * seconds_per_beat
        instrument.notes.append(
            pretty_midi.Note(
                velocity=int(event.get("velocity") or 100),
                pitch=int(event["midi"]),
                start=start,
                end=end,
            )
        )
    midi.instruments.append(instrument)

    import io

    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()


def analyze_sketch(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate a sketch payload and run full musical analysis.

    Returns (result, errors); result is None when validation fails.
    """
    sketch, errors = validate_sketch_payload(payload)
    if sketch is None:
        return None, errors
    sample = sketch_to_sample(sketch)
    context = build_musical_context(sample)
    return (
        {
            "sketch": sketch,
            "sample": sample,
            "context": context,
            "out_of_scale_notes": out_of_scale_notes(sketch),
        },
        [],
    )
