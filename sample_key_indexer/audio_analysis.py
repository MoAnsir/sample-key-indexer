from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

from sample_key_indexer.classify import classify_sample
from sample_key_indexer.models import AnalysisResult, file_signature

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
DRUM_OR_NOISE_TYPES = {"Kick", "Snare", "Hat", "Perc", "DrumLoops", "FX", "FXLoops"}
FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
ENGINE_PRESETS = {
    "fast": ("librosa",),
    "balanced": ("librosa", "essentia"),
    "deep": ("librosa", "essentia"),
}


def validate_audio_backend(engines: tuple[str, ...] | None = None) -> list[str]:
    import lzma

    import librosa
    import numpy
    import soundfile

    _ = (lzma, librosa, numpy, soundfile)
    warnings: list[str] = []
    for engine in engines or ("librosa",):
        if engine == "essentia" and not _essentia_available():
            warnings.append("Essentia is not installed; V2 will keep using librosa-only decisions for now.")
    return warnings


def analyze_file(
    path: Path,
    analysis_duration: float = 30.0,
    sample_rate: int = 22050,
    analysis_profile: str = "fast",
    engines: tuple[str, ...] | None = None,
) -> AnalysisResult:
    try:
        with warnings.catch_warnings(record=True) as captured_warnings:
            warnings.simplefilter("always")
            result = _analyze_file(path, analysis_duration, sample_rate, analysis_profile, engines)
        warning_messages = summarize_warnings(captured_warnings)
        if warning_messages:
            result = replace(result, analysis_warnings=unique_strings([*result.analysis_warnings, *warning_messages]))
        return result
    except Exception as exc:
        return _error_result(path, str(exc))


def _analyze_file(
    path: Path,
    analysis_duration: float,
    sample_rate: int,
    analysis_profile: str,
    engines: tuple[str, ...] | None,
) -> AnalysisResult:
    import librosa

    selected_engines = normalize_engines(analysis_profile, engines)
    analysis_warnings: list[str] = []
    y, sr = librosa.load(path, sr=sample_rate, mono=True, duration=analysis_duration)
    if y.size == 0:
        return _error_result(path, "empty audio")

    duration, original_sample_rate = audio_file_info(path, fallback_duration=float(librosa.get_duration(y=y, sr=sr)), fallback_sr=sr)
    tiny_reason = tiny_audio_reason(y, sr, duration)
    if tiny_reason:
        return tiny_audio_result(path, y, sr, duration, original_sample_rate, selected_engines, analysis_profile, tiny_reason)

    root_note, root_confidence, fundamental_freq = detect_root_note(y, sr)
    key, key_confidence = detect_key(y, sr, root_note)
    category, sample_type = classify_sample(path, duration, y, sr)
    confidence = confidence_for(root_confidence, key_confidence, sample_type, key)
    filename_key = detect_filename_key(path)
    features = extract_audio_features(y, sr, fundamental_freq)
    notes = detect_notes(y, sr)
    filename_bpm = detect_filename_bpm(path)
    bpm, bpm_review_reasons = detect_bpm_with_review(y, sr, duration, expected_bpm=filename_bpm)
    signature = file_signature(path)
    essentia_key, essentia_root, essentia_confidence, essentia_warning = analyze_with_essentia(y, sr, selected_engines)
    if essentia_warning:
        analysis_warnings.append(essentia_warning)
    final_key, final_root, final_confidence, review_reasons = choose_consensus_key(
        librosa_key=key,
        librosa_root=root_note,
        librosa_confidence=confidence,
        librosa_key_confidence=key_confidence,
        librosa_root_confidence=root_confidence,
        essentia_key=essentia_key,
        essentia_root=essentia_root,
        essentia_confidence=essentia_confidence,
        filename_key=filename_key,
        sample_type=sample_type,
    )
    review_reasons = [*review_reasons, *bpm_review_reasons]
    final_scale_confidence = key_confidence
    if final_key == essentia_key:
        final_scale_confidence = max(final_scale_confidence, essentia_confidence)

    return AnalysisResult(
        file_path=str(path),
        root_note=final_root,
        key=final_key,
        confidence=final_confidence,
        category=category,
        type=sample_type,
        sample_rate=original_sample_rate,
        format=path.suffix.lower().lstrip("."),
        scale_confidence=round(final_scale_confidence, 3),
        notes=notes,
        chords=estimate_chords(final_key, notes, duration, category),
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
        essentia_root=essentia_root,
        essentia_key=essentia_key,
        essentia_key_confidence=essentia_confidence,
        filename_key=filename_key,
        analysis_profile=analysis_profile,
        analysis_engines=list(selected_engines),
        analysis_warnings=analysis_warnings,
        needs_review=bool(review_reasons),
        review_reasons=review_reasons,
        duration=round(duration, 3),
        size=int(signature["size"]),
        mtime=float(signature["mtime"]),
    )


def audio_file_info(path: Path, fallback_duration: float, fallback_sr: int) -> tuple[float, int]:
    try:
        import soundfile as sf

        info = sf.info(path)
        return round(float(info.frames / info.samplerate), 3), int(info.samplerate)
    except Exception:
        return round(float(fallback_duration), 3), int(fallback_sr)


def tiny_audio_reason(y: np.ndarray, sr: int, duration: float) -> str | None:
    import numpy as np

    if duration < 0.08 or y.size < int(sr * 0.08):
        return "tiny_audio"
    if float(np.nanmax(np.abs(y))) < 1e-5:
        return "near_silence"
    return None


def tiny_audio_result(
    path: Path,
    y: np.ndarray,
    sr: int,
    duration: float,
    original_sample_rate: int,
    selected_engines: tuple[str, ...],
    analysis_profile: str,
    reason: str,
) -> AnalysisResult:
    import numpy as np

    category, sample_type = classify_sample(path, duration, None, None)
    signature = file_signature(path)
    peak_amp = float(np.nanmax(np.abs(y))) if y.size else 0.0
    rms_amp = float(np.sqrt(np.nanmean(np.square(y)))) if y.size else 0.0
    filename_key = detect_filename_key(path)
    return AnalysisResult(
        file_path=str(path),
        root_note=None,
        key=None,
        confidence=0.0,
        category=category,
        type=sample_type,
        sample_rate=original_sample_rate,
        format=path.suffix.lower().lstrip("."),
        filename_key=filename_key,
        analysis_profile=analysis_profile,
        analysis_engines=list(selected_engines),
        analysis_warnings=[reason],
        needs_review=True,
        review_reasons=[reason],
        duration=round(duration, 3),
        rms_db=round(_amp_to_db(rms_amp), 2),
        peak_db=round(_amp_to_db(peak_amp), 2),
        dynamic_range_db=round(max(0.0, _amp_to_db(peak_amp) - _amp_to_db(rms_amp)), 2),
        brightness="unknown",
        warmth="unknown",
        roughness="unknown",
        size=int(signature["size"]),
        mtime=float(signature["mtime"]),
    )


def summarize_warnings(captured_warnings: list[warnings.WarningMessage]) -> list[str]:
    messages: list[str] = []
    for warning in captured_warnings:
        text = str(warning.message)
        if "PySoundFile failed. Trying audioread instead." in text:
            messages.append("decoder_fallback_audioread")
        elif "n_fft=" in text and "too large for input signal" in text:
            messages.append("short_signal_fft_adjusted")
        elif "Trying to estimate tuning from empty frequency set" in text:
            messages.append("empty_frequency_set")
        else:
            messages.append(f"{warning.category.__name__}: {text}")
    return unique_strings(messages)


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def quick_audio_duration(path: Path) -> float | None:
    try:
        import soundfile as sf

        info = sf.info(path)
        return round(float(info.frames / info.samplerate), 3)
    except Exception:
        try:
            import librosa

            return round(float(librosa.get_duration(path=str(path))), 3)
        except Exception:
            return None


def normalize_engines(analysis_profile: str, engines: tuple[str, ...] | None = None) -> tuple[str, ...]:
    if engines:
        selected = engines
    else:
        selected = ENGINE_PRESETS.get(analysis_profile, ENGINE_PRESETS["fast"])
    normalized: list[str] = []
    for engine in selected:
        engine_name = engine.strip().lower()
        if engine_name and engine_name not in normalized:
            normalized.append(engine_name)
    if "librosa" not in normalized:
        normalized.insert(0, "librosa")
    return tuple(normalized)


def analyze_with_essentia(y: np.ndarray, sr: int, engines: tuple[str, ...]) -> tuple[str | None, str | None, float, str | None]:
    if "essentia" not in engines:
        return None, None, 0.0, None
    try:
        import numpy as np
        from essentia.standard import KeyExtractor

        audio = np.asarray(y, dtype="float32")
        key, scale, strength = KeyExtractor(sampleRate=sr)(audio)
        normalized_key = _normalise_key_name(key, scale)
        root = key if key in NOTE_NAMES else None
        return normalized_key, root, round(float(strength), 3), None
    except ModuleNotFoundError:
        return None, None, 0.0, "essentia unavailable"
    except Exception as exc:
        return None, None, 0.0, f"essentia failed: {exc}"


def detect_filename_key(path: Path) -> str | None:
    name = path.stem
    text = re.sub(r"[_\-.]+", " ", name)
    note = r"(?P<note>[A-Ga-g])(?P<accidental>#|b)?"
    minor = r"(?:min(?:or)?|m)"
    major = r"(?:maj(?:or)?|major)"
    patterns = (
        rf"(?<![A-Za-z]){note}\s+{minor}(?![A-Za-z])",
        rf"(?<![A-Za-z]){note}\s+{major}(?![A-Za-z])",
        rf"(?<![A-Za-z]){note}{minor}(?![A-Za-z])",
        rf"(?<![A-Za-z]){note}{major}(?![A-Za-z])",
        rf"\(({note})\)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            note_name = _normalise_note(match.group("note"), match.groupdict().get("accidental"))
            if not note_name:
                continue
            token = match.group(0).lower()
            if "min" in token or token.rstrip(")").endswith("m"):
                return f"{note_name}_minor"
            if "maj" in token or "major" in token:
                return f"{note_name}_major"
            return note_name
    return None


def detect_filename_bpm(path: Path) -> float | None:
    name = path.stem
    patterns = (
        r"(?<!\d)(?P<bpm>\d{2,3})\s*bpm(?![A-Za-z])",
        r"(?<!\d)(?P<bpm>\d{2,3})(?!\d)",
    )
    for pattern in patterns:
        matches: list[float] = []
        for match in re.finditer(pattern, name, flags=re.IGNORECASE):
            value = float(match.group("bpm"))
            if 40 <= value <= 240:
                matches.append(value)
        if matches:
            return matches[-1]
    return None


def choose_consensus_key(
    librosa_key: str | None,
    librosa_root: str | None,
    librosa_confidence: float,
    librosa_key_confidence: float,
    librosa_root_confidence: float,
    essentia_key: str | None,
    essentia_root: str | None,
    essentia_confidence: float,
    filename_key: str | None,
    sample_type: str,
) -> tuple[str | None, str | None, float, list[str]]:
    review_reasons = review_reasons_for(
        librosa_key=librosa_key,
        librosa_root=librosa_root,
        librosa_root_confidence=librosa_root_confidence,
        essentia_key=essentia_key,
        essentia_root=essentia_root,
        filename_key=filename_key,
        sample_type=sample_type,
    )
    if essentia_key and librosa_key == essentia_key:
        final_root = root_from_key(librosa_key) or librosa_root or essentia_root
        final_confidence = round(min(1.0, max(librosa_confidence, essentia_confidence) + 0.08), 3)
        return librosa_key, final_root, final_confidence, key_review_reasons_with_severity(review_reasons, librosa_key, final_confidence, filename_key, sample_type)
    if (
        essentia_key
        and not librosa_key
        and essentia_root
        and librosa_root == essentia_root
        and librosa_key_confidence >= 0.85
        and librosa_root_confidence >= 0.4
        and sample_type not in DRUM_OR_NOISE_TYPES
    ):
        confidence = max(essentia_confidence * 0.85, min(0.84, (essentia_confidence + librosa_key_confidence) / 2))
        final_confidence = round(confidence, 3)
        return essentia_key, root_from_key(essentia_key) or essentia_root, final_confidence, key_review_reasons_with_severity(review_reasons, essentia_key, final_confidence, filename_key, sample_type)
    if essentia_key and not librosa_key and essentia_confidence >= 0.45:
        final_root = root_from_key(essentia_key) or essentia_root or librosa_root
        final_confidence = round(min(1.0, essentia_confidence * 0.85), 3)
        return essentia_key, final_root, final_confidence, key_review_reasons_with_severity(review_reasons, essentia_key, final_confidence, filename_key, sample_type)
    if essentia_key and librosa_key and essentia_confidence > librosa_confidence + 0.2:
        final_root = root_from_key(essentia_key) or essentia_root or librosa_root
        final_confidence = round(min(1.0, essentia_confidence * 0.8), 3)
        return essentia_key, final_root, final_confidence, key_review_reasons_with_severity(review_reasons, essentia_key, final_confidence, filename_key, sample_type)
    return librosa_key, root_from_key(librosa_key) or librosa_root, librosa_confidence, key_review_reasons_with_severity(review_reasons, librosa_key, librosa_confidence, filename_key, sample_type)


def review_reasons_for(
    librosa_key: str | None,
    librosa_root: str | None,
    librosa_root_confidence: float,
    essentia_key: str | None,
    essentia_root: str | None,
    filename_key: str | None,
    sample_type: str,
) -> list[str]:
    reasons: list[str] = []
    if librosa_key and essentia_key and librosa_key != essentia_key:
        reasons.append("engine_key_disagreement")
    if (
        not librosa_key
        and librosa_root
        and essentia_root
        and librosa_root != essentia_root
        and librosa_root_confidence >= 0.3
        and sample_type not in DRUM_OR_NOISE_TYPES
    ):
        reasons.append("engine_root_disagreement")
    if filename_key and sample_type not in DRUM_OR_NOISE_TYPES:
        engine_keys = [key for key in (librosa_key, essentia_key) if key]
        if engine_keys and filename_key not in engine_keys:
            reasons.append("filename_key_disagreement")
    return reasons


def key_review_reasons_with_severity(
    reasons: list[str],
    final_key: str | None,
    final_confidence: float,
    filename_key: str | None,
    sample_type: str,
) -> list[str]:
    if not filename_key or sample_type in DRUM_OR_NOISE_TYPES or not final_key or final_key == filename_key:
        return reasons
    if "filename_key_disagreement" not in reasons:
        return reasons
    severity = "filename_key_disagreement_confident" if final_confidence >= 0.75 else "filename_key_disagreement_weak"
    return [*reasons, severity]


def _essentia_available() -> bool:
    try:
        import essentia.standard  # noqa: F401
    except Exception:
        return False
    return True


def _normalise_key_name(key: str, scale: str) -> str | None:
    if key not in NOTE_NAMES:
        return None
    mode = scale.lower()
    if mode not in {"major", "minor"}:
        return key
    return f"{key}_{mode}"


def root_from_key(key: str | None) -> str | None:
    if not key:
        return None
    root = key.split("_", maxsplit=1)[0]
    if root in NOTE_NAMES:
        return root
    return None


def _normalise_note(note: str, accidental: str | None) -> str | None:
    note_name = note.upper()
    if accidental:
        note_name = f"{note_name}{accidental}"
    note_name = FLAT_TO_SHARP.get(note_name, note_name)
    if note_name not in NOTE_NAMES:
        return None
    return note_name


def extract_audio_features(y: np.ndarray, sr: int, fundamental_freq: float | None) -> dict:
    import librosa
    import numpy as np

    n_fft = _adaptive_n_fft(y)
    rms = librosa.feature.rms(y=y, frame_length=n_fft)
    rms_amp = float(np.nanmean(rms))
    peak_amp = float(np.nanmax(np.abs(y)))
    rms_db = _amp_to_db(rms_amp)
    peak_db = _amp_to_db(peak_amp)
    centroid = float(np.nanmean(librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=n_fft)))
    bandwidth = float(np.nanmean(librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=n_fft)))
    rolloff = float(np.nanmean(librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=n_fft)))
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=n_fft)
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


def detect_bpm(y: np.ndarray, sr: int, duration: float, expected_bpm: float | None = None) -> float | None:
    bpm, _ = detect_bpm_with_review(y, sr, duration, expected_bpm)
    return bpm


def detect_bpm_with_review(y: np.ndarray, sr: int, duration: float, expected_bpm: float | None = None) -> tuple[float | None, list[str]]:
    if duration < 2.0:
        return None, []
    try:
        import librosa
        import numpy as np

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        value = float(np.asarray(tempo).reshape(-1)[0])
        if value <= 0:
            return None, []
        normalized, reason = _normalise_bpm_with_reason(value, expected_bpm)
        return round(normalized, 2), ([reason] if reason else [])
    except Exception:
        return None, []


def _normalise_bpm(value: float, expected_bpm: float | None = None) -> float:
    normalized, _ = _normalise_bpm_with_reason(value, expected_bpm)
    return normalized


def _normalise_bpm_with_reason(value: float, expected_bpm: float | None = None) -> tuple[float, str | None]:
    if value <= 0:
        return value, None
    candidates = [value]
    for factor in (0.25, 0.5, 2.0, 4.0):
        candidate = value * factor
        if 40 <= candidate <= 220:
            candidates.append(candidate)
    if expected_bpm:
        closest = min(candidates, key=lambda candidate: abs(candidate - expected_bpm))
        if abs(closest - expected_bpm) / expected_bpm <= 0.12:
            return expected_bpm, None
        if abs(closest - expected_bpm) / expected_bpm > 0.15:
            return expected_bpm, "filename_bpm_anchor"
    in_range = [candidate for candidate in candidates if 40 <= candidate <= 220]
    if in_range:
        return min(in_range, key=lambda candidate: abs(candidate - min(max(value, 70), 180))), None
    return value, None


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
        return None, 0.0, None
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


def _adaptive_n_fft(y: np.ndarray) -> int:
    import numpy as np

    length = int(y.size)
    if length <= 0:
        return 16
    if length >= 2048:
        return 2048
    return max(16, 2 ** int(np.floor(np.log2(length))))


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
