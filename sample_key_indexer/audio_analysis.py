from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

from sample_key_indexer.classify import classify_sample
from sample_key_indexer.models import AnalysisResult, file_signature

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)


def validate_audio_backend() -> None:
    import lzma

    import librosa
    import numpy
    import soundfile

    _ = (lzma, librosa, numpy, soundfile)


def analyze_file(path: Path, analysis_duration: float = 30.0, sample_rate: int = 22050) -> AnalysisResult:
    try:
        import librosa

        y, sr = librosa.load(path, sr=sample_rate, mono=True, duration=analysis_duration)
        if y.size == 0:
            return _error_result(path, "empty audio")

        duration, original_sample_rate = audio_file_info(path, fallback_duration=float(librosa.get_duration(y=y, sr=sr)), fallback_sr=sr)
        root_note, root_confidence, fundamental_freq = detect_root_note(y, sr)
        key, key_confidence = detect_key(y, sr, root_note)
        category, sample_type = classify_sample(path, duration, y, sr)
        confidence = confidence_for(root_confidence, key_confidence, sample_type, key)
        features = extract_audio_features(y, sr, fundamental_freq)
        notes = detect_notes(y, sr)
        bpm = detect_bpm(y, sr, duration)
        signature = file_signature(path)

        return AnalysisResult(
            file_path=str(path),
            root_note=root_note,
            key=key,
            confidence=confidence,
            category=category,
            type=sample_type,
            sample_rate=original_sample_rate,
            format=path.suffix.lower().lstrip("."),
            scale_confidence=key_confidence,
            notes=notes,
            chords=estimate_chords(key, notes, duration, category),
            bpm=bpm,
            rms_db=features["rms_db"],
            peak_db=features["peak_db"],
            dynamic_range_db=features["dynamic_range_db"],
            spectral_centroid=features["spectral_centroid"],
            spectral_bandwidth=features["spectral_bandwidth"],
            rolloff=features["rolloff"],
            fundamental_freq=features["fundamental_freq"],
            brightness=features["brightness"],
            warmth=features["warmth"],
            roughness=features["roughness"],
            mfcc=features["mfcc"],
            subtype=estimate_subtype(sample_type, path),
            source=estimate_source(sample_type, path),
            librosa_root=root_note,
            librosa_root_confidence=root_confidence,
            librosa_key=key,
            librosa_key_confidence=key_confidence,
            duration=round(duration, 3),
            size=int(signature["size"]),
            mtime=float(signature["mtime"]),
        )
    except Exception as exc:
        return _error_result(path, str(exc))


def audio_file_info(path: Path, fallback_duration: float, fallback_sr: int) -> tuple[float, int]:
    try:
        import soundfile as sf

        info = sf.info(path)
        return round(float(info.frames / info.samplerate), 3), int(info.samplerate)
    except Exception:
        return round(float(fallback_duration), 3), int(fallback_sr)


def extract_audio_features(y: np.ndarray, sr: int, fundamental_freq: float | None) -> dict:
    import librosa
    import numpy as np

    rms = librosa.feature.rms(y=y)
    rms_amp = float(np.nanmean(rms))
    peak_amp = float(np.nanmax(np.abs(y)))
    rms_db = _amp_to_db(rms_amp)
    peak_db = _amp_to_db(peak_amp)
    centroid = float(np.nanmean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    bandwidth = float(np.nanmean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
    rolloff = float(np.nanmean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = [round(float(value), 4) for value in np.nanmean(mfcc, axis=1)]
    roughness_value = float(np.nanvar(librosa.feature.zero_crossing_rate(y)))
    low_energy, total_energy = _low_frequency_energy(y, sr)

    return {
        "rms_db": round(rms_db, 2),
        "peak_db": round(peak_db, 2),
        "dynamic_range_db": round(max(0.0, peak_db - rms_db), 2),
        "spectral_centroid": round(centroid, 2),
        "spectral_bandwidth": round(bandwidth, 2),
        "rolloff": round(rolloff, 2),
        "fundamental_freq": round(float(fundamental_freq), 2) if fundamental_freq else None,
        "brightness": _bucket(centroid, 1200, 3200),
        "warmth": _bucket(low_energy / max(total_energy, 1e-12), 0.22, 0.45),
        "roughness": _bucket(roughness_value, 0.0015, 0.006),
        "mfcc": mfcc_mean,
    }


def detect_notes(y: np.ndarray, sr: int, limit: int = 5) -> list[str]:
    import librosa
    import numpy as np

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_sum = np.nan_to_num(chroma.sum(axis=1))
    if float(chroma_sum.sum()) <= 0:
        return []
    indexes = np.argsort(chroma_sum)[::-1][:limit]
    return [NOTE_NAMES[int(index)] for index in indexes if chroma_sum[int(index)] > 0]


def detect_bpm(y: np.ndarray, sr: int, duration: float) -> float | None:
    if duration < 2.0:
        return None
    try:
        import librosa
        import numpy as np

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        value = float(np.asarray(tempo).reshape(-1)[0])
        if value <= 0:
            return None
        return round(value, 2)
    except Exception:
        return None


def detect_root_note(y: np.ndarray, sr: int) -> tuple[str | None, float, float | None]:
    import librosa
    import numpy as np

    harmonic, _ = librosa.effects.hpss(y)
    target = harmonic if np.mean(np.abs(harmonic)) > 1e-5 else y

    f0 = librosa.yin(target, fmin=librosa.note_to_hz("C1"), fmax=librosa.note_to_hz("C8"), sr=sr)
    voiced = f0[np.isfinite(f0)]
    voiced = voiced[(voiced > 0) & (voiced < librosa.note_to_hz("C8"))]

    if voiced.size >= 3:
        midi = np.rint(librosa.hz_to_midi(voiced)).astype(int) % 12
        counts = np.bincount(midi, minlength=12)
        root_idx = int(np.argmax(counts))
        confidence = float(counts[root_idx] / max(1, counts.sum()))
        root_freq = float(np.nanmedian(voiced[midi == root_idx])) if np.any(midi == root_idx) else None
        return NOTE_NAMES[root_idx], round(min(1.0, confidence), 3), root_freq

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_sum = np.nan_to_num(chroma.sum(axis=1))
    if float(chroma_sum.sum()) <= 0:
        return None, 0.0
    root_idx = int(np.argmax(chroma_sum))
    confidence = float(chroma_sum[root_idx] / chroma_sum.sum())
    return NOTE_NAMES[root_idx], round(min(1.0, confidence), 3), None


def detect_key(y: np.ndarray, sr: int, root_note: str | None) -> tuple[str | None, float]:
    if root_note is None:
        return None, 0.0

    import librosa
    import numpy as np

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_sum = np.nan_to_num(chroma.sum(axis=1)).astype(float)
    if float(chroma_sum.sum()) <= 0:
        return None, 0.0

    chroma_norm = chroma_sum / np.linalg.norm(chroma_sum)
    major_scores = _profile_scores(chroma_norm, MAJOR_PROFILE)
    minor_scores = _profile_scores(chroma_norm, MINOR_PROFILE)

    major_idx = int(np.argmax(major_scores))
    minor_idx = int(np.argmax(minor_scores))
    major_score = float(major_scores[major_idx])
    minor_score = float(minor_scores[minor_idx])

    if abs(major_score - minor_score) < 0.03:
        return None, round(max(major_score, minor_score), 3)

    mode = "major" if major_score > minor_score else "minor"
    idx = major_idx if mode == "major" else minor_idx
    if NOTE_NAMES[idx] != root_note and max(major_score, minor_score) < 0.86:
        return None, round(max(major_score, minor_score), 3)

    return f"{NOTE_NAMES[idx]}_{mode}", round(max(major_score, minor_score), 3)


def confidence_for(root_confidence: float, key_confidence: float, sample_type: str, key: str | None) -> float:
    type_factor = {
        "Kick": 0.45,
        "Snare": 0.4,
        "Hat": 0.3,
        "Perc": 0.45,
        "DrumLoops": 0.55,
        "FX": 0.5,
        "FXLoops": 0.5,
        "Bass": 0.8,
        "BassLoops": 0.8,
        "Vocals": 0.85,
        "VocalLoops": 0.85,
    }.get(sample_type, 0.9)
    base = key_confidence if key else root_confidence
    return round(max(0.0, min(1.0, base * type_factor)), 3)


def _profile_scores(chroma_norm: np.ndarray, profile: np.ndarray) -> np.ndarray:
    import numpy as np

    profile_array = np.array(profile)
    profile_norm = profile_array / np.linalg.norm(profile_array)
    return np.array([float(np.dot(chroma_norm, np.roll(profile_norm, shift))) for shift in range(12)])


def estimate_chords(key: str | None, notes: list[str], duration: float, category: str) -> list[str]:
    if category != "Loops" or duration < 2.0:
        return []
    if key and "_" in key:
        root, mode = key.split("_", 1)
        return [f"{root}m" if mode == "minor" else root]
    return notes[:3]


def estimate_subtype(sample_type: str, path: Path) -> str | None:
    name = path.stem.lower()
    if sample_type in {"Pads", "MelodyLoops"} and any(token in name for token in ("dark", "ambient", "atmo")):
        return "AmbientPad"
    if sample_type in {"Bass", "BassLoops"} and "808" in name:
        return "808"
    return sample_type


def estimate_source(sample_type: str, path: Path) -> str:
    name = path.stem.lower()
    if sample_type in {"Vocals", "VocalLoops"} or any(token in name for token in ("vocal", "vox", "voice")):
        return "speech"
    if sample_type in {"Kick", "Snare", "Hat", "Perc", "DrumLoops"}:
        return "drum"
    if sample_type in {"FX", "FXLoops"} or any(token in name for token in ("noise", "field", "foley")):
        return "noise"
    return "synth"


def _amp_to_db(value: float) -> float:
    import numpy as np

    return float(20.0 * np.log10(max(value, 1e-12)))


def _bucket(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "medium"


def _low_frequency_energy(y: np.ndarray, sr: int) -> tuple[float, float]:
    import numpy as np

    spectrum = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(y.size, d=1 / sr)
    total = float(np.sum(spectrum))
    low = float(np.sum(spectrum[freqs <= 250]))
    return low, total


def _error_result(path: Path, error: str) -> AnalysisResult:
    signature = file_signature(path) if path.exists() else {"size": None, "mtime": None}
    return AnalysisResult(
        file_path=str(path),
        root_note=None,
        key=None,
        confidence=0.0,
        category="OneShots",
        type="FX",
        duration=0.0,
        format=path.suffix.lower().lstrip("."),
        error=error,
        size=signature["size"],
        mtime=signature["mtime"],
    )
