from __future__ import annotations

from typing import Any

from sample_key_indexer.music_theory import NOTE_ORDER, FLAT_TO_SHARP, related_key_targets

# ---------------------------------------------------------------------------
# Frequency-slot complementarity map
# sketch register → sample types that complement it
# ---------------------------------------------------------------------------
_FREQ_COMPLEMENTS: dict[str, set[str]] = {
    "sub":  {"Kick", "Bass", "Perc", "Percussion", "Synth", "Pads"},
    "low":  {"Kick", "Bass", "Perc", "Percussion", "Synth", "Pads"},
    "mid":  {"Keys", "Synth", "Pads", "Guitar", "Pluck", "Lead", "Vocals", "FX"},
    "high": {"Tops", "Perc", "Percussion", "Cymbals", "FX", "Foley", "Vocals", "SFX"},
}
_DEFAULT_COMPLEMENTS: set[str] = {"Synth", "Pads", "Keys", "Lead"}


def _normalize_key(raw: str | None) -> tuple[str, str] | None:
    """Return (tonic, mode) from a key string like 'C#_minor', or None."""
    if not raw:
        return None
    raw = str(raw).strip()
    if "_" not in raw:
        return None
    tonic_raw, mode = raw.split("_", 1)
    tonic = tonic_raw.strip()
    tonic = FLAT_TO_SHARP.get(tonic, tonic)
    mode = mode.lower().strip()
    if tonic not in NOTE_ORDER or mode not in ("major", "minor"):
        return None
    return tonic, mode


def score_key(sample: dict[str, Any], sketch: dict[str, Any], weight: float = 0.4) -> tuple[float, list[str]]:
    """Score key compatibility between a sample and a sketch."""
    sample_key = _normalize_key(sample.get("key"))
    sketch_tonic = sketch.get("tonic") or ""
    sketch_mode = sketch.get("mode") or ""
    if not sample_key or not sketch_tonic or not sketch_mode:
        return 0.0, []

    targets = related_key_targets(sketch_tonic, sketch_mode)
    target_map = {t["key"]: t["label"] for t in targets}
    sample_key_str = f"{sample_key[0]}_{sample_key[1]}"

    label = target_map.get(sample_key_str, "")
    if label == "Same key":
        return weight * 1.0, ["same key"]
    if label == "Relative key":
        return weight * 0.7, ["relative key"]
    if label in ("Dominant move", "Subdominant move"):
        return weight * 0.5, [label.lower()]
    if label == "Parallel color":
        return weight * 0.3, ["parallel color"]

    return 0.0, []


def score_freq(sample: dict[str, Any], sketch: dict[str, Any], weight: float = 0.25) -> tuple[float, list[str]]:
    """Score frequency slot complementarity."""
    register = str(sketch.get("frequency_register") or "").lower()
    sample_type = str(sample.get("type") or "")
    if not register or not sample_type:
        return 0.0, []
    complements = _FREQ_COMPLEMENTS.get(register, _DEFAULT_COMPLEMENTS)
    if sample_type in complements:
        return weight * 1.0, [f"fills {register}s"]
    return 0.0, []


def score_mood(sample: dict[str, Any], sketch: dict[str, Any], weight: float = 0.2) -> tuple[float, list[str]]:
    """Score mood match using brightness/warmth vs sketch transition vocabulary."""
    brightness = str(sample.get("brightness") or "").lower()
    warmth = str(sample.get("warmth") or "").lower()
    # Sketch context carries transition_suggestions mood labels in the analysis
    # result, but for cross-matching we work from the raw sketch dict which
    # has tonic/mode — map to a rough mood bucket.
    mode = str(sketch.get("mode") or "").lower()
    # Heuristic: minor mode sketches benefit from warm/dark/neutral samples
    # major mode sketches benefit from bright/warm/neutral samples
    if mode == "minor":
        positive = {"warm", "dark", "neutral", "mellow"}
    else:
        positive = {"bright", "warm", "neutral", "airy"}

    matched = []
    if brightness in positive:
        matched.append(f"{brightness} brightness")
    if warmth in positive:
        matched.append(f"{warmth} warmth")

    if matched:
        return weight * (1.0 if len(matched) >= 2 else 0.6), matched
    return 0.0, []


def score_bpm(sample: dict[str, Any], sketch: dict[str, Any], weight: float = 0.15) -> tuple[float, list[str]]:
    """Score BPM proximity, including halftime and doubletime."""
    sample_bpm = sample.get("bpm")
    sketch_bpm = sketch.get("bpm")
    if not sample_bpm or not sketch_bpm:
        return 0.0, []
    s_bpm = float(sample_bpm)
    k_bpm = float(sketch_bpm)
    if s_bpm <= 0 or k_bpm <= 0:
        return 0.0, []

    for candidate, label in [
        (k_bpm, "same BPM"),
        (k_bpm / 2, "halftime"),
        (k_bpm * 2, "doubletime"),
    ]:
        diff = abs(s_bpm - candidate)
        if diff <= 5:
            return weight * 1.0, [label]
        if diff <= 10:
            return weight * 0.5, [f"near {label}"]

    return 0.0, []


def score_sample(
    sample: dict[str, Any],
    sketch: dict[str, Any],
    filters: dict[str, bool] | None = None,
) -> tuple[float, list[str]]:
    """Compute a composite match score [0, 1] and a list of match reasons."""
    f = filters or {}
    total = 0.0
    reasons: list[str] = []

    if f.get("key_compat", True):
        s, r = score_key(sample, sketch)
        total += s
        reasons.extend(r)
    if f.get("freq_slot", True):
        s, r = score_freq(sample, sketch)
        total += s
        reasons.extend(r)
    if f.get("mood", True):
        s, r = score_mood(sample, sketch)
        total += s
        reasons.extend(r)
    if f.get("bpm", True):
        s, r = score_bpm(sample, sketch)
        total += s
        reasons.extend(r)

    return min(1.0, total), reasons


def cross_match(
    sketch: dict[str, Any],
    samples: list[dict[str, Any]],
    top_n: int = 50,
    filters: dict[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """Score all samples against a sketch and return top_n with score + reasons."""
    scored = []
    for sample in samples:
        # Skip sketch entries themselves
        if sample.get("source_kind") == "sketch":
            continue
        score, reasons = score_sample(sample, sketch, filters)
        if score > 0:
            scored.append((score, reasons, sample))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {**s, "score": round(sc, 4), "match_reasons": r}
        for sc, r, s in scored[:top_n]
    ]
