from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

ONESHOT_THRESHOLD_SECONDS = 2.0

DRUM_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Kick", ("kick", "kicks", "bd", "bass drum", "bassdrum", "kik")),
    ("Snare", ("snare", "snares", "sd", "rim", "clap")),
    ("Hat", ("hat", "hats", "hihat", "hi hat", "hh", "closed hat", "closedhat", "open hat", "openhat", "cymbal", "ride", "crash")),
    ("Perc", ("perc", "percussion", "conga", "bongo", "tom", "shaker", "clave", "cowbell", "tabla", "dholak", "duff", "timbale", "timbales", "tambourine", "cabassa")),
]

TONAL_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Bass", ("bass", "808", "sub")),
    ("Chords", ("chord", "stab", "keys", "piano", "organ", "rhodes")),
    ("Leads", ("lead", "melody", "melodic", "synth", "horn", "horns", "brass")),
    ("Pads", ("pad", "atmo", "atmos", "drone", "texture")),
    ("Plucks", ("pluck", "arp", "arpeggio")),
    ("Vocals", ("vocal", "vox", "voice", "chant", "choir")),
    ("FX", ("fx", "sfx", "riser", "downlifter", "impact", "sweep", "noise")),
]

MELODIC_INSTRUMENT_TOKENS: tuple[str, ...] = (
    "accordion",
    "cello",
    "flute",
    "guitar",
    "mandolin",
    "mandolines",
    "sax",
    "saxophone",
    "strings",
    "trumpet",
    "violin",
    "woodwind",
)
LOOP_PATTERNS: tuple[str, ...] = (
    "loop",
    "loops",
    "groove",
    "break",
    "breakbeat",
    "beat",
    "beats",
    "bpm",
    "fill",
    "fills",
    "roll",
    "pattern",
    "ptn",
    "phrase",
    "riff",
)
ONESHOT_PATTERNS: tuple[str, ...] = ("one shot", "oneshot", "hit", "single")
DRUM_LOOP_PATTERNS: tuple[str, ...] = (
    "drum loop",
    "drumloop",
    "drums",
    "drum",
    "beat",
    "beats",
    "breakbeat",
    "break",
    "fill",
    "fills",
    "roll",
)


def category_from_duration_and_name(duration: float, path: Path) -> str:
    stem_text, folder_text = _path_text(path)
    loop_score = _score_patterns(stem_text, folder_text, LOOP_PATTERNS)
    oneshot_score = _score_patterns(stem_text, folder_text, ONESHOT_PATTERNS)
    if loop_score > oneshot_score:
        return "Loops"
    return "OneShots" if duration < ONESHOT_THRESHOLD_SECONDS else "Loops"


def classify_sample(path: Path, duration: float, y: np.ndarray | None = None, sr: int | None = None) -> tuple[str, str]:
    category = category_from_duration_and_name(duration, path)
    stem_text, folder_text = _path_text(path)
    full_text = f"{stem_text} {folder_text}".strip()

    drum_loop_score = _score_patterns(stem_text, folder_text, DRUM_LOOP_PATTERNS)
    drum_type, drum_type_score = _best_pattern_match(stem_text, folder_text, DRUM_PATTERNS)
    tonal_type, tonal_type_score = _best_pattern_match(stem_text, folder_text, TONAL_PATTERNS)

    if category == "Loops" and drum_loop_score > 0 and drum_loop_score >= tonal_type_score:
        return category, "DrumLoops"

    if drum_type and drum_type_score >= tonal_type_score:
        return category, _loop_type(category, drum_type, is_drum=True)

    if tonal_type:
        return category, _loop_type(category, tonal_type, is_drum=False)

    if y is not None and sr is not None and y.size:
        feature_type = _feature_type(category, y, sr)
        if feature_type in {"Bass", "BassLoops", "FX", "FXLoops"} and _has_melodic_instrument_name(full_text):
            return category, "MelodyLoops" if category == "Loops" else "Leads"
        return category, feature_type

    if _has_melodic_instrument_name(full_text):
        return category, "MelodyLoops" if category == "Loops" else "Leads"
    return category, "FXLoops" if category == "Loops" else "FX"


def _feature_type(category: str, y: np.ndarray, sr: int) -> str:
    import librosa
    import numpy as np

    harmonic, percussive = librosa.effects.hpss(y)
    harmonic_energy = float(np.mean(np.abs(harmonic)))
    percussive_energy = float(np.mean(np.abs(percussive)))
    centroid = float(np.nanmean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    zcr = float(np.nanmean(librosa.feature.zero_crossing_rate(y)))

    if percussive_energy > harmonic_energy * 1.5:
        if centroid > 5500 or zcr > 0.16:
            return "Hat" if category == "OneShots" else "DrumLoops"
        return "Perc" if category == "OneShots" else "DrumLoops"

    if centroid < 1000:
        return "BassLoops" if category == "Loops" else "Bass"
    if centroid < 2600:
        return "MelodyLoops" if category == "Loops" else "Chords"
    return "FXLoops" if category == "Loops" else "Leads"


def _loop_type(category: str, sample_type: str, is_drum: bool) -> str:
    if category == "OneShots":
        return sample_type
    if is_drum:
        return "DrumLoops"
    if sample_type == "Bass":
        return "BassLoops"
    if sample_type == "Vocals":
        return "VocalLoops"
    if sample_type == "FX":
        return "FXLoops"
    return "MelodyLoops"


def _path_text(path: Path) -> tuple[str, str]:
    return _normalise_text(path.stem), _normalise_text(" ".join(path.parts[-4:-1]))


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-./()]+", " ", value.lower())).strip()


def _score_patterns(stem_text: str, folder_text: str, patterns: tuple[str, ...]) -> int:
    stem_tokens = set(stem_text.split())
    folder_tokens = set(folder_text.split())
    score = 0
    for pattern in patterns:
        if _matches_pattern(stem_text, stem_tokens, pattern):
            score += 4
        if _matches_pattern(folder_text, folder_tokens, pattern):
            score += 1
    return score


def _best_pattern_match(
    stem_text: str,
    folder_text: str,
    pattern_groups: list[tuple[str, tuple[str, ...]]],
) -> tuple[str | None, int]:
    best_type: str | None = None
    best_score = 0
    for sample_type, patterns in pattern_groups:
        score = _score_patterns(stem_text, folder_text, patterns)
        if score > best_score:
            best_type = sample_type
            best_score = score
    return best_type, best_score


def _matches_pattern(text: str, tokens: set[str], pattern: str) -> bool:
    pattern = _normalise_text(pattern)
    if not pattern:
        return False
    if " " in pattern:
        return pattern in text
    return pattern in tokens


def _has_melodic_instrument_name(name: str) -> bool:
    return any(token in name for token in MELODIC_INSTRUMENT_TOKENS)
