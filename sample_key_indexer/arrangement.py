from __future__ import annotations

import io
import random
from typing import Any

from sample_key_indexer.music_theory import NOTE_ORDER, SCALE_PATTERNS


# ---------------------------------------------------------------------------
# Strategy helpers (pure functions — no side effects)
# ---------------------------------------------------------------------------

def humanize(events: list[dict], amount: float = 0.12, seed: int = 0) -> list[dict]:
    """Add ±amount×127 velocity jitter per note. Seeded so results are
    reproducible for the same sketch/section combination."""
    rng = random.Random(seed)
    out = []
    for ev in events:
        jitter = int(rng.uniform(-amount * 127, amount * 127))
        vel = max(1, min(127, int(ev.get("velocity") or 100) + jitter))
        out.append({**ev, "velocity": vel})
    return out


def transpose_diatonic(
    events: list[dict],
    tonic: str,
    mode: str,
    steps: int,
) -> list[dict]:
    """Shift notes by `steps` diatonic scale steps (positive = up).
    Clamps at MIDI 0–127; preserves octave position."""
    if tonic not in NOTE_ORDER or mode not in SCALE_PATTERNS:
        return events
    root = NOTE_ORDER.index(tonic)
    intervals = SCALE_PATTERNS[mode]
    # Build a sorted list of all MIDI pitches in the scale across the full range
    scale_midis: list[int] = []
    for octave in range(-1, 11):
        for interval in intervals:
            m = (octave + 1) * 12 + (root + interval) % 12
            if 0 <= m <= 127:
                scale_midis.append(m)
    scale_midis.sort()

    out = []
    for ev in events:
        midi = int(ev.get("midi") or ev.get("note") or 60)
        # Find nearest scale pitch
        nearest = min(scale_midis, key=lambda m: abs(m - midi))
        try:
            idx = scale_midis.index(nearest)
        except ValueError:
            out.append(ev)
            continue
        new_idx = max(0, min(len(scale_midis) - 1, idx + steps))
        new_midi = scale_midis[new_idx]
        out.append({**ev, "midi": new_midi})
    return out


def make_fill(events: list[dict], beats_per_bar: int, density: float = 0.5, seed: int = 0) -> list[dict]:
    """On the last beat of the section, replace notes with a density-scaled
    subset of the original events, offset to the last beat."""
    if not events:
        return events
    last_end = max(e["start"] + e["duration"] for e in events)
    last_bar_start = (int(last_end / beats_per_bar) * beats_per_bar)
    last_beat = last_bar_start + beats_per_bar - 1

    rng = random.Random(seed)
    fill_pool = [e for e in events if e["start"] < beats_per_bar]
    fill_pool = rng.sample(fill_pool, max(1, int(len(fill_pool) * density)))
    fill_events = [{**e, "start": last_beat + (e["start"] % 1)} for e in fill_pool]
    main_events = [e for e in events if not (e["start"] >= last_beat and e["start"] < last_end)]
    return main_events + fill_events


def make_sparse(events: list[dict], beats_per_bar: int, keep_ratio: float = 0.33) -> list[dict]:
    """Keep only root-note (lowest MIDI) and first beat of each bar — 'breakdown' feel."""
    if not events:
        return events
    by_bar: dict[int, list[dict]] = {}
    for ev in events:
        bar = int(ev["start"] / beats_per_bar)
        by_bar.setdefault(bar, []).append(ev)
    out = []
    for bar_events in by_bar.values():
        bar_events_sorted = sorted(bar_events, key=lambda e: (e["start"], e.get("midi", 60)))
        # Keep lowest-pitched note on first beat only
        first_beat = min(e["start"] for e in bar_events_sorted)
        on_first = [e for e in bar_events_sorted if abs(e["start"] - first_beat) < 0.01]
        if on_first:
            out.append(min(on_first, key=lambda e: e.get("midi", 60)))
        # Plus a random keep_ratio of other notes
        others = [e for e in bar_events_sorted if e not in out]
        keep_n = max(0, int(len(others) * keep_ratio))
        out.extend(sorted(others, key=lambda e: e["start"])[:keep_n])
    return sorted(out, key=lambda e: (e["start"], e.get("midi", 60)))


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def _extend_events(events: list[dict], source_bars: int, target_bars: int, beats_per_bar: int) -> list[dict]:
    """Tile the source note events to fill target_bars."""
    if source_bars <= 0:
        return events
    source_beats = source_bars * beats_per_bar
    target_beats = target_bars * beats_per_bar
    out = []
    repeat = 0
    while repeat * source_beats < target_beats:
        offset = repeat * source_beats
        for ev in events:
            new_start = ev["start"] + offset
            if new_start >= target_beats:
                break
            out.append({**ev, "start": round(new_start, 6)})
        repeat += 1
    return out


def build_arrangement(
    sketch: dict[str, Any],
    target_bars: int = 16,
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    """Expand a sketch to `target_bars` with optional variation strategies.

    Returns a dict with `sections` (list of labelled bar ranges + events),
    `total_bars`, `bpm`, `beats_per_bar`, `tonic`, `mode`.

    Supported strategies: "humanize", "fill", "ab", "sparse"
    """
    strategies = set(strategies or [])
    bpm = float(sketch.get("bpm") or 120)
    beats_per_bar = int(sketch.get("beats_per_bar") or 4)
    source_bars = int(sketch.get("bars") or 8)
    tonic = sketch.get("tonic") or ""
    mode = sketch.get("mode") or "minor"
    base_events: list[dict] = list(sketch.get("note_events") or [])

    # Normalise: ensure events have "midi" key
    normed: list[dict] = []
    for ev in base_events:
        midi = ev.get("midi")
        if midi is None:
            note = ev.get("note")
            if isinstance(note, int):
                midi = note
            else:
                midi = 60
        normed.append({**ev, "midi": int(midi)})
    base_events = normed

    # Tile to target
    full_events = _extend_events(base_events, source_bars, target_bars, beats_per_bar)
    seed = hash(sketch.get("name") or "") & 0xFFFF

    sections: list[dict[str, Any]] = []

    if "ab" in strategies and target_bars >= 8:
        # A section: first half, B section: transposed +4th, optional breakdown
        half = target_bars // 2
        a_end = half
        b_end = target_bars - (2 if "sparse" in strategies else 0)
        breakdown_start = b_end

        a_events = _extend_events(base_events, source_bars, a_end, beats_per_bar)
        if "humanize" in strategies:
            a_events = humanize(a_events, seed=seed)
        if "fill" in strategies:
            a_events = make_fill(a_events, beats_per_bar, seed=seed)

        diatonic_steps = 2 if mode == "major" else 3  # up a 4th diatonically
        b_raw = _extend_events(base_events, source_bars, a_end, beats_per_bar)
        b_events_shifted = []
        for ev in transpose_diatonic(b_raw, tonic, mode, diatonic_steps):
            b_events_shifted.append({**ev, "start": round(ev["start"] + a_end * beats_per_bar, 6)})
        if "humanize" in strategies:
            b_events_shifted = humanize(b_events_shifted, seed=seed + 1)

        sections.append({
            "label": "A",
            "bar_start": 0,
            "bar_end": a_end,
            "variation": "original" + ("+humanize" if "humanize" in strategies else ""),
            "note_events": a_events,
        })
        sections.append({
            "label": "B",
            "bar_start": a_end,
            "bar_end": b_end,
            "variation": "transpose_4th" + ("+humanize" if "humanize" in strategies else ""),
            "note_events": b_events_shifted,
        })

        if "sparse" in strategies and breakdown_start < target_bars:
            breakdown_raw = _extend_events(base_events, source_bars, 2, beats_per_bar)
            breakdown_events = make_sparse(breakdown_raw, beats_per_bar)
            offset = breakdown_start * beats_per_bar
            breakdown_events = [{**ev, "start": round(ev["start"] + offset, 6)} for ev in breakdown_events]
            sections.append({
                "label": "Breakdown",
                "bar_start": breakdown_start,
                "bar_end": target_bars,
                "variation": "sparse",
                "note_events": breakdown_events,
            })
    else:
        # No A/B — single section with requested strategies applied
        events = full_events
        variation = "original"
        if "humanize" in strategies:
            events = humanize(events, seed=seed)
            variation = "humanize"
        if "fill" in strategies:
            events = make_fill(events, beats_per_bar, seed=seed)
            variation += "+fill"
        if "sparse" in strategies:
            events = make_sparse(events, beats_per_bar)
            variation = "sparse"
        sections.append({
            "label": "Main",
            "bar_start": 0,
            "bar_end": target_bars,
            "variation": variation.strip("+"),
            "note_events": events,
        })

    return {
        "sections": sections,
        "total_bars": target_bars,
        "bpm": bpm,
        "beats_per_bar": beats_per_bar,
        "tonic": tonic,
        "mode": mode,
    }


def midi_bytes_for_arrangement(arrangement: dict[str, Any], name: str = "Arrangement") -> bytes:
    """Render an arrangement (from build_arrangement) to a flat single-track MIDI file."""
    try:
        import pretty_midi
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"missing_backend:{exc}") from exc

    bpm = float(arrangement.get("bpm") or 120)
    beats_per_bar = int(arrangement.get("beats_per_bar") or 4)
    seconds_per_beat = 60.0 / max(1.0, bpm)

    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    midi.time_signature_changes.append(
        pretty_midi.TimeSignature(beats_per_bar, 4, 0.0)
    )
    instrument = pretty_midi.Instrument(program=0, name=name)

    for section in arrangement.get("sections") or []:
        for ev in section.get("note_events") or []:
            start_s = float(ev["start"]) * seconds_per_beat
            end_s = start_s + max(1 / 32, float(ev.get("duration") or 0.5)) * seconds_per_beat
            instrument.notes.append(
                pretty_midi.Note(
                    velocity=max(1, min(127, int(ev.get("velocity") or 100))),
                    pitch=max(0, min(127, int(ev.get("midi") or 60))),
                    start=start_s,
                    end=end_s,
                )
            )

    midi.instruments.append(instrument)
    buf = io.BytesIO()
    midi.write(buf)
    return buf.getvalue()
