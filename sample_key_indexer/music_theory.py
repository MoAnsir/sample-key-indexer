from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NOTE_ORDER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

SCALE_PATTERNS: dict[str, list[int]] = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}

ROMAN_NUMERALS: dict[str, list[str]] = {
    "major": ["I", "ii", "iii", "IV", "V", "vi"],
    "minor": ["i", "III", "iv", "v", "VI", "VII"],
}

PROGRESSION_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "major": [
        {"name": "Lift", "degrees": [0, 4, 5, 3], "mood": "uplifting", "notes_order": [0, 2, 4, 5, 4, 2, 0]},
        {"name": "Anthem", "degrees": [0, 3, 4, 5], "mood": "bright", "notes_order": [0, 4, 5, 4, 3, 2, 0]},
        {"name": "Drive", "degrees": [0, 5, 3, 4], "mood": "confident", "notes_order": [0, 1, 2, 4, 5, 4, 2]},
    ],
    "minor": [
        {"name": "Tension", "degrees": [0, 5, 3, 4], "mood": "dark", "notes_order": [0, 2, 3, 4, 6, 4, 3]},
        {"name": "Melancholy", "degrees": [0, 2, 5, 4], "mood": "melancholic", "notes_order": [0, 2, 3, 5, 6, 5, 3]},
        {"name": "Cinematic", "degrees": [0, 3, 5, 4], "mood": "cinematic", "notes_order": [0, 1, 3, 4, 6, 4, 1]},
    ],
}

TRANSITION_RULES: dict[str, list[str]] = {
    "dark": ["tense", "cinematic", "brooding", "aggressive"],
    "melancholic": ["dreamy", "nostalgic", "cinematic", "warm"],
    "uplifting": ["bright", "hopeful", "anthemic", "euphoric"],
    "bright": ["uplifting", "hopeful", "energetic", "playful"],
    "cinematic": ["tense", "melancholic", "epic", "brooding"],
    "confident": ["aggressive", "uplifting", "driving", "tense"],
    "percussive": ["driving", "aggressive", "tribal", "kinetic"],
    "neutral": ["bright", "dark", "dreamy", "tense"],
}


@dataclass(frozen=True)
class KeyDescriptor:
    tonic: str | None
    mode: str | None


def normalize_note(note: Any) -> str:
    if note is None:
        return ""
    cleaned = str(note).strip().replace("♭", "b").replace("♯", "#")
    if not cleaned:
        return ""
    if len(cleaned) >= 2 and cleaned[1] in {"b", "#"}:
        token = cleaned[0].upper() + cleaned[1:]
    else:
        token = cleaned[0].upper() + cleaned[1:].lower()
    token = FLAT_TO_SHARP.get(token, token)
    return token if token in NOTE_ORDER else ""


def key_descriptor(key: Any) -> KeyDescriptor:
    if not key:
        return KeyDescriptor(None, None)
    raw = str(key)
    if "_" in raw:
        tonic, mode = raw.split("_", 1)
        tonic = normalize_note(tonic)
        mode = mode.lower().strip()
        if mode not in SCALE_PATTERNS:
            mode = "minor" if "min" in mode else "major" if "maj" in mode else None
        return KeyDescriptor(tonic or None, mode)
    tonic = normalize_note(raw)
    return KeyDescriptor(tonic or None, None)


def scale_notes(tonic: str, mode: str) -> list[str]:
    tonic = normalize_note(tonic)
    if tonic not in NOTE_ORDER or mode not in SCALE_PATTERNS:
        return []
    root_index = NOTE_ORDER.index(tonic)
    return [NOTE_ORDER[(root_index + step) % 12] for step in SCALE_PATTERNS[mode]]


def chord_name(root: str, quality: str) -> str:
    if quality == "minor":
        return f"{root}m"
    if quality == "dim":
        return f"{root}dim"
    return root


def diatonic_chords(tonic: str, mode: str) -> list[str]:
    notes = scale_notes(tonic, mode)
    if not notes:
        return []
    if mode == "major":
        qualities = ["major", "minor", "minor", "major", "major", "minor"]
    else:
        qualities = ["minor", "dim", "major", "minor", "minor", "major"]
    return [chord_name(notes[idx], quality) for idx, quality in enumerate(qualities)]


def _ordered_unique_notes(values: list[Any]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = normalize_note(str(value).rstrip("0123456789")) if isinstance(value, str) else normalize_note(value)
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def infer_musical_record(sample: dict[str, Any]) -> dict[str, Any]:
    descriptor = key_descriptor(sample.get("deep_key") or sample.get("key"))
    tonic = normalize_note(sample.get("deep_root") or sample.get("root_note") or descriptor.tonic)
    mode = descriptor.mode or ("minor" if str(sample.get("deep_key") or sample.get("key") or "").endswith("_minor") else "major")
    notes = _ordered_unique_notes((sample.get("deep_notes") or []) + (sample.get("notes") or []))
    if not notes and tonic and mode:
        notes = scale_notes(tonic, mode)
    chords = [str(item) for item in (sample.get("deep_chords") or sample.get("chords") or []) if item]
    bpm = sample.get("deep_bpm") if sample.get("deep_bpm") is not None else sample.get("bpm")
    key_name = f"{tonic}_{mode}" if tonic and mode else (sample.get("deep_key") or sample.get("key"))
    scale = f"{tonic} {mode}" if tonic and mode else None
    return {
        "tonic": tonic or None,
        "mode": mode or None,
        "key": key_name,
        "scale": scale,
        "notes": notes,
        "note_events": sample.get("deep_note_events") or [],
        "chords": chords,
        "bpm": bpm,
        "ticks": sample.get("deep_ticks") or [],
        "tuning_hz": sample.get("deep_tuning_hz"),
        "confidence": sample.get("deep_analysis_confidence") or sample.get("deep_key_confidence") or sample.get("confidence"),
        "route": sample.get("deep_route_family"),
    }


def related_key_targets(tonic: str, mode: str) -> list[dict[str, Any]]:
    tonic = normalize_note(tonic)
    if tonic not in NOTE_ORDER or mode not in SCALE_PATTERNS:
        return []
    root_index = NOTE_ORDER.index(tonic)
    relative = NOTE_ORDER[(root_index + (3 if mode == "minor" else 9)) % 12]
    fifth = NOTE_ORDER[(root_index + 7) % 12]
    fourth = NOTE_ORDER[(root_index + 5) % 12]
    parallel_mode = "major" if mode == "minor" else "minor"
    targets = [
        ("Same key", tonic, mode),
        ("Relative key", relative, "major" if mode == "minor" else "minor"),
        ("Dominant move", fifth, mode),
        ("Subdominant move", fourth, mode),
        ("Parallel color", tonic, parallel_mode),
    ]
    return [
        {
            "label": label,
            "key": f"{target_tonic}_{target_mode}",
            "scale": f"{target_tonic} {target_mode}",
            "notes": scale_notes(target_tonic, target_mode),
            "chords": diatonic_chords(target_tonic, target_mode),
        }
        for label, target_tonic, target_mode in targets
    ]


def progression_suggestions(musical_record: dict[str, Any]) -> list[dict[str, Any]]:
    tonic = musical_record.get("tonic")
    mode = musical_record.get("mode")
    if not tonic or mode not in PROGRESSION_TEMPLATES:
        return []
    scale = scale_notes(tonic, mode)
    chords = diatonic_chords(tonic, mode)
    romans = ROMAN_NUMERALS[mode]
    suggestions: list[dict[str, Any]] = []
    for template in PROGRESSION_TEMPLATES[mode]:
        chord_sequence = [chords[idx] for idx in template["degrees"] if idx < len(chords)]
        roman_sequence = [romans[idx] for idx in template["degrees"] if idx < len(romans)]
        note_order = [scale[idx] for idx in template["notes_order"] if idx < len(scale)]
        suggestions.append(
            {
                "name": template["name"],
                "mood": template["mood"],
                "progression": chord_sequence,
                "roman": roman_sequence,
                "notes_to_play": note_order,
                "play_order": note_order,
            }
        )
    return suggestions


def infer_mood(sample: dict[str, Any], musical_record: dict[str, Any]) -> dict[str, Any]:
    mode = musical_record.get("mode")
    bpm = float(musical_record.get("bpm") or 0.0)
    brightness = str(sample.get("brightness") or "").lower()
    warmth = str(sample.get("warmth") or "").lower()
    sample_type = str(sample.get("type") or "")
    route = str(musical_record.get("route") or "")

    primary = "neutral"
    reasons: list[str] = []
    if route in {"percussive", "percussive_pitched"} or sample_type in {"DrumLoops", "Perc", "Kick", "Snare", "Hat"}:
        primary = "percussive"
        reasons.append("percussive_route")
    elif mode == "minor":
        primary = "dark" if bpm >= 100 else "melancholic"
        reasons.append("minor_mode")
    elif mode == "major":
        primary = "uplifting" if bpm >= 110 else "bright"
        reasons.append("major_mode")

    if brightness == "high" and primary in {"dark", "melancholic"}:
        primary = "cinematic"
        reasons.append("high_brightness")
    if warmth == "high" and primary == "bright":
        primary = "hopeful"
        reasons.append("high_warmth")
    if bpm >= 128 and primary in {"uplifting", "bright"}:
        primary = "energetic"
        reasons.append("high_bpm")
    elif bpm and bpm < 90 and primary in {"dark", "melancholic"}:
        primary = "dreamy"
        reasons.append("low_bpm")

    transitions = TRANSITION_RULES.get(primary, TRANSITION_RULES["neutral"])
    return {
        "primary": primary,
        "supporting": transitions[:3],
        "transitions": transitions,
        "reasons": reasons,
    }


def build_musical_context(sample: dict[str, Any]) -> dict[str, Any]:
    musical_record = infer_musical_record(sample)
    compat_keys = related_key_targets(musical_record.get("tonic") or "", musical_record.get("mode") or "")
    progressions = progression_suggestions(musical_record)
    mood = infer_mood(sample, musical_record)
    transitions = [
        {
            "label": label,
            "why": f"{mood['primary']} material usually moves well into {label} textures.",
        }
        for label in mood.get("transitions", [])
    ]
    return {
        "musical_record": musical_record,
        "compatibility": {
            "keys": compat_keys,
            "progressions": progressions,
        },
        "mood_profile": mood,
        "transition_suggestions": transitions,
    }


def midi_bytes_for_progression(sample: dict[str, Any], progression_index: int = 0) -> bytes:
    try:
        import pretty_midi
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"missing_backend:{exc}") from exc
    context = build_musical_context(sample)
    musical_record = context["musical_record"]
    progressions = context["compatibility"]["progressions"]
    if not progressions:
        raise RuntimeError("no_progression_available")
    chosen = progressions[max(0, min(progression_index, len(progressions) - 1))]
    bpm = float(musical_record.get("bpm") or 120.0)
    seconds_per_beat = 60.0 / max(1.0, bpm)
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    instrument = pretty_midi.Instrument(program=0, name="Sample Key Indexer Progression")
    tonic = musical_record.get("tonic")
    mode = musical_record.get("mode")
    scale = scale_notes(tonic or "C", mode or "major")
    scale_octave = {note: 60 + NOTE_ORDER.index(note) for note in scale}
    current_time = 0.0
    for chord_name_value in chosen["progression"]:
        note_root = normalize_note(chord_name_value.rstrip("mdi"))
        is_minor = chord_name_value.endswith("m") and not chord_name_value.endswith("dim")
        root_pitch = scale_octave.get(note_root, 60)
        intervals = [0, 3, 7] if is_minor else [0, 4, 7]
        duration = seconds_per_beat * 2
        for interval in intervals:
            instrument.notes.append(
                pretty_midi.Note(
                    velocity=88,
                    pitch=root_pitch + interval,
                    start=current_time,
                    end=current_time + duration,
                )
            )
        current_time += duration
    midi.instruments.append(instrument)
    import io

    buffer = io.BytesIO()
    midi.write(buffer)
    return buffer.getvalue()
