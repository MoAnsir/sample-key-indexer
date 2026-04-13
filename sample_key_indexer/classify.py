from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

ONESHOT_THRESHOLD_SECONDS = 2.0

DRUM_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Kick", ("kick", "bd", "bass drum", "bassdrum", "kik")),
    ("Snare", ("snare", "sd", "rim", "clap")),
    ("Hat", ("hat", "hihat", "hi hat", "hh", "closedhat", "openhat", "cymbal", "ride", "crash")),
    ("Perc", ("perc", "percussion", "conga", "bongo", "tom", "shaker", "clave", "cowbell")),
]

TONAL_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("Bass", ("bass", "808", "sub")),
    ("Chords", ("chord", "stab", "keys", "piano", "organ", "rhodes")),
    ("Leads", ("lead", "melody", "melodic", "synth")),
    ("Pads", ("pad", "atmo", "atmos", "drone", "texture")),
    ("Plucks", ("pluck", "arp", "arpeggio")),
    ("Vocals", ("vocal", "vox", "voice", "chant", "choir")),
    ("FX", ("fx", "sfx", "riser", "downlifter", "impact", "sweep", "noise")),
]

LOOP_PATTERNS: tuple[str, ...] = ("loop", "groove", "break", "beat", "bpm")


def category_from_duration_and_name(duration: float, path: Path) -> str:
    name = _normalise_name(path)
    if any(token in name for token in LOOP_PATTERNS):
        return "Loops"
    return "OneShots" if duration < ONESHOT_THRESHOLD_SECONDS else "Loops"


def classify_sample(path: Path, duration: float, y: np.ndarray | None = None, sr: int | None = None) -> tuple[str, str]:
    category = category_from_duration_and_name(duration, path)
    name = _normalise_name(path)

    for sample_type, tokens in DRUM_PATTERNS:
        if any(token in name for token in tokens):
            return category, _loop_type(category, sample_type, is_drum=True)

    for sample_type, tokens in TONAL_PATTERNS:
        if any(token in name for token in tokens):
            return category, _loop_type(category, sample_type, is_drum=False)

    if y is not None and sr is not None and y.size:
        return category, _feature_type(category, y, sr)

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


def _normalise_name(path: Path) -> str:
    name = f"{path.stem} {' '.join(path.parts[-4:-1])}".lower()
    return re.sub(r"[_\-.]+", " ", name)
