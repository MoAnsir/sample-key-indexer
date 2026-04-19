from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sample_key_indexer.audio_analysis import analyze_file, normalize_engines
from sample_key_indexer.index_store import MetadataIndex, SQLiteMetadataIndex, load_records
from sample_key_indexer.web_app import _flatten_sample, _playback_info, _playable_path, parse_library_roots

NON_HARMONIC_REVIEW_TYPES = {"Kick", "Snare", "Hat", "Perc", "DrumLoops", "FX", "FXLoops"}
NON_HARMONIC_REVIEW_TEXT = (
    "indian percussion",
    "percussion",
    "dholak",
    "khanjira",
    "kanjira",
    "idakka",
    "udakai",
    "tabla",
    "dhol",
    "mridangam",
    "ghatam",
    "duff",
    "duf",
    "daf",
)
DEEP_BACKEND_COMMANDS = (
    {
        "id": "keyfinder",
        "label": "KeyFinder CLI",
        "commands": ("keyfinder-cli", "keyfinder"),
        "version_args": ("--version",),
        "purpose": "External harmonic key detection.",
        "required": True,
    },
    {
        "id": "sonic_annotator",
        "label": "Sonic Annotator",
        "commands": ("sonic-annotator",),
        "version_args": ("--version",),
        "purpose": "Vamp plugin runner for QM key/chord plugins.",
        "required": False,
    },
    {
        "id": "aubio",
        "label": "aubio",
        "commands": ("aubio",),
        "version_args": ("--version",),
        "purpose": "Small-footprint onset/tempo utility, not a primary key backend.",
        "required": False,
    },
)
VAMP_PLUGIN_DIRS = (
    Path("~/Library/Audio/Plug-Ins/Vamp").expanduser(),
    Path("/Library/Audio/Plug-Ins/Vamp"),
    Path("/opt/homebrew/lib/vamp"),
    Path("/usr/local/lib/vamp"),
)
FLAT_TO_SHARP = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}
AUDIT_DRUM_LOOP_TOKENS = ("drum", "beat", "beats", "fill", "fills", "roll", "breakbeat", "break")
AUDIT_LOOP_TOKENS = ("loop", "loops", "bpm", "ptn", "pattern", "phrase", "riff", "groove", "beat", "beats", "fill", "fills", "roll")
AUDIT_ONESHOT_TOKENS = ("one shot", "oneshot", "hit", "single")
AUDIT_TYPE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Kick", ("kick", "kicks", "bd", "bass drum", "bassdrum", "kik")),
    ("Snare", ("snare", "snares", "sd", "rim", "clap")),
    ("Hat", ("hat", "hats", "hihat", "hi hat", "hh", "closed hat", "closedhat", "open hat", "openhat", "cymbal", "ride", "crash")),
    ("Perc", ("perc", "percussion", "conga", "bongo", "tom", "shaker", "clave", "cowbell")),
    ("Bass", ("bass", "808", "sub")),
    ("Chords", ("chord", "stab", "keys", "piano", "organ", "rhodes")),
    ("Leads", ("lead", "melody", "melodic", "synth")),
    ("Pads", ("pad", "atmo", "atmos", "drone", "texture")),
    ("Plucks", ("pluck", "arp", "arpeggio")),
    ("Vocals", ("vocal", "vox", "voice", "chant", "choir")),
    ("FX", ("fx", "sfx", "riser", "downlifter", "impact", "sweep", "noise")),
)
AUDIT_TYPE_TO_LOOP_TYPE = {
    "Kick": "DrumLoops",
    "Snare": "DrumLoops",
    "Hat": "DrumLoops",
    "Perc": "DrumLoops",
    "Bass": "BassLoops",
    "Vocals": "VocalLoops",
    "FX": "FXLoops",
}


def build_review_summary(records: list[dict[str, Any]], max_examples: int = 10) -> dict[str, Any]:
    samples = [_flatten_sample(record) for record in records]
    review_samples = [sample for sample in samples if sample.get("needs_review")]
    reason_counts = Counter(reason for sample in review_samples for reason in sample.get("review_reasons", []))
    type_counts = Counter(sample.get("type") or "Unknown" for sample in review_samples)
    examples = sorted(review_samples, key=lambda sample: (sample.get("confidence") or 0.0, sample.get("name") or ""))[:max_examples]

    return {
        "total": len(samples),
        "needs_review": len(review_samples),
        "review_percentage": _percentage(len(review_samples), len(samples)),
        "reasons": [{"reason": reason, "count": count} for reason, count in reason_counts.most_common()],
        "types": [{"type": sample_type, "count": count} for sample_type, count in type_counts.most_common()],
        "examples": [
            {
                "name": sample.get("name"),
                "key": sample.get("key"),
                "root": sample.get("root_note"),
                "confidence": sample.get("confidence"),
                "reasons": sample.get("review_reasons", []),
                "path": sample.get("file_path"),
            }
            for sample in examples
        ],
    }


def select_deep_review_candidates(
    records: list[dict[str, Any]],
    low_confidence: float = 0.35,
    include_warnings: bool = True,
    include_errors: bool = True,
    limit: int = 0,
    retry_deep_failed: bool = False,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        sample = _flatten_sample(record)
        if deep_review_failed(sample) and not retry_deep_failed:
            continue
        reasons = deep_review_reasons(sample, low_confidence, include_warnings, include_errors)
        if not reasons:
            continue
        candidate = dict(sample)
        candidate["deep_review_reasons"] = reasons
        candidates.append(candidate)
    candidates.sort(key=lambda sample: (selection_priority(sample), sample.get("confidence") or 0.0, sample.get("name") or ""))
    if limit > 0:
        return candidates[:limit]
    return candidates


def deep_review_failed(sample: dict[str, Any]) -> bool:
    return bool((sample.get("deep_review") or {}).get("failed"))


def deep_review_reasons(sample: dict[str, Any], low_confidence: float, include_warnings: bool, include_errors: bool) -> list[str]:
    reasons: list[str] = []
    confidence = sample.get("confidence")
    review_reasons = sample.get("review_reasons") or []
    warnings = sample.get("analysis_warnings") or []
    if include_warnings and warnings:
        reasons.append("analysis_warnings")
    if sample.get("needs_review"):
        reasons.append("needs_review")
    if confidence is None or float(confidence) < low_confidence:
        reasons.append("low_confidence")
    if any("key_disagreement" in reason or "root_disagreement" in reason for reason in review_reasons):
        reasons.append("key_or_root_disagreement")
    if include_errors and sample.get("error"):
        reasons.append("analysis_error")
    if is_non_harmonic_review_sample(sample):
        return [reason for reason in reasons if reason in {"analysis_warnings", "analysis_error"}]
    return reasons


def is_non_harmonic_review_sample(sample: dict[str, Any]) -> bool:
    if (sample.get("type") or "") in NON_HARMONIC_REVIEW_TYPES:
        return True
    searchable_text = " ".join(
        str(part or "").lower()
        for part in (
            sample.get("name"),
            sample.get("relative_path"),
            sample.get("file_path"),
        )
    )
    return any(token in searchable_text for token in NON_HARMONIC_REVIEW_TEXT)


def selection_priority(sample: dict[str, Any]) -> int:
    reasons = sample.get("deep_review_reasons") or []
    if "analysis_error" in reasons:
        return 0
    if "key_or_root_disagreement" in reasons:
        return 1
    if "low_confidence" in reasons:
        return 2
    if "needs_review" in reasons:
        return 3
    return 4


def build_deep_review_plan(
    records: list[dict[str, Any]],
    low_confidence: float = 0.35,
    limit: int = 0,
    retry_deep_failed: bool = False,
) -> dict[str, Any]:
    samples = [_flatten_sample(record) for record in records]
    skipped_failed = 0 if retry_deep_failed else sum(1 for sample in samples if deep_review_failed(sample))
    candidates = select_deep_review_candidates(records, low_confidence=low_confidence, limit=limit, retry_deep_failed=retry_deep_failed)
    reason_counts = Counter(reason for sample in candidates for reason in sample.get("deep_review_reasons", []))
    return {
        "selected": len(candidates),
        "low_confidence": low_confidence,
        "skipped_deep_failed": skipped_failed,
        "retry_deep_failed": retry_deep_failed,
        "reasons": [{"reason": reason, "count": count} for reason, count in reason_counts.most_common()],
        "examples": [
            {
                "name": sample.get("name"),
                "key": sample.get("key"),
                "confidence": sample.get("confidence"),
                "selection_reasons": sample.get("deep_review_reasons", []),
                "path": sample.get("file_path"),
            }
            for sample in candidates[:10]
        ],
        "candidates": candidates,
    }


def build_deep_failure_report(records: list[dict[str, Any]], max_examples: int = 20) -> dict[str, Any]:
    samples = [_flatten_sample(record) for record in records]
    failures = [deep_failure_item(sample) for sample in samples if deep_review_failed(sample)]
    failures.sort(key=lambda item: (item["reason"], item["library_id"] or "", item["relative_path"] or item["name"] or ""))
    return {
        "total": len(failures),
        "by_reason": count_items(failures, "reason"),
        "by_library": count_items(failures, "library_id"),
        "by_format": count_items(failures, "format"),
        "by_type": count_items(failures, "type"),
        "by_duration": count_items(failures, "duration_bucket"),
        "by_path_family": count_items(failures, "path_family"),
        "triage_hints": deep_failure_triage_hints(failures),
        "examples": failures[:max(0, max_examples)],
        "failures": failures,
    }


def build_backend_check_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    failure_report = build_deep_failure_report(records, max_examples=0)
    backend_status = discover_deep_backends()
    return {
        "deep_failure_targets": {
            "total": failure_report["total"],
            "by_reason": failure_report["by_reason"],
            "by_format": failure_report["by_format"],
            "by_duration": failure_report["by_duration"],
            "by_path_family": failure_report["by_path_family"],
            "triage_hints": failure_report["triage_hints"],
        },
        "backend_status": backend_status,
        "missing_required_backends": [
            backend for backend in backend_status["commands"] if backend.get("required") and backend.get("status") != "available"
        ],
    }


def build_keyfinder_comparison_report(records: list[dict[str, Any]], max_examples: int = 20) -> dict[str, Any]:
    samples = [_flatten_sample(record) for record in records]
    items = [keyfinder_comparison_item(sample) for sample in samples]
    enriched = [item for item in items if item["has_keyfinder"]]
    successes = [item for item in enriched if item["status"] == "success"]
    errors = [item for item in enriched if item["status"] != "success"]
    disagreements = [item for item in successes if not item["matches_stored_key"] and not item["matches_stored_root"]]
    root_only_matches = [item for item in successes if not item["matches_stored_key"] and item["matches_stored_root"]]
    return {
        "total": len(samples),
        "enriched": len(enriched),
        "missing_keyfinder": len(samples) - len(enriched),
        "successes": len(successes),
        "errors": len(errors),
        "conversion_used": sum(1 for item in enriched if item["conversion_used"]),
        "matches_stored_key": sum(1 for item in successes if item["matches_stored_key"]),
        "matches_stored_root": sum(1 for item in successes if item["matches_stored_root"]),
        "root_only_matches": len(root_only_matches),
        "key_and_root_disagreements": len(disagreements),
        "by_library": aggregate_keyfinder_group(enriched, "library_id"),
        "by_type": aggregate_keyfinder_group(enriched, "type"),
        "by_confidence": aggregate_keyfinder_group(enriched, "confidence_bucket"),
        "by_status": count_items(enriched, "status"),
        "by_decision": count_items(successes, "decision"),
        "disagreement_examples": sorted(
            disagreements,
            key=lambda item: (-(item.get("confidence") or 0.0), item.get("library_id") or "", item.get("name") or ""),
        )[:max(0, max_examples)],
        "root_only_examples": sorted(
            root_only_matches,
            key=lambda item: (-(item.get("confidence") or 0.0), item.get("library_id") or "", item.get("name") or ""),
        )[:max(0, max_examples)],
        "missing_examples": [
            {
                "name": sample.get("name"),
                "library_id": sample.get("library_id"),
                "type": sample.get("type"),
                "confidence": sample.get("confidence"),
                "relative_path": sample.get("relative_path"),
            }
            for sample in samples
            if not keyfinder_external(sample)
        ][:max(0, max_examples)],
    }


def build_classification_audit_report(records: list[dict[str, Any]], max_examples: int = 20) -> dict[str, Any]:
    samples = [_flatten_sample(record) for record in records]
    items = [classification_audit_item(sample) for sample in samples]
    suspicious = [item for item in items if item["reasons"]]
    suspicious.sort(key=lambda item: (-len(item["reasons"]), item["library_id"], item["relative_path"] or item["name"] or ""))
    return {
        "total": len(samples),
        "suspicious": len(suspicious),
        "by_reason": count_reason_items(suspicious),
        "by_library": count_items(suspicious, "library_id"),
        "by_type": count_items(suspicious, "stored_type"),
        "by_path_family": count_items(suspicious, "path_family"),
        "examples": suspicious[:max(0, max_examples)],
        "items": suspicious,
    }


def build_keyfinder_review_policy_report(records: list[dict[str, Any]], high_confidence: float = 0.75, max_examples: int = 20) -> dict[str, Any]:
    samples = [_flatten_sample(record) for record in records]
    items = [keyfinder_review_policy_item(sample, high_confidence) for sample in samples]
    enriched = [item for item in items if item["has_keyfinder"]]
    successes = [item for item in enriched if item["status"] == "success"]
    action_items = [item for item in successes if item["action"] == "add_review"]
    return {
        "mode": "review_only",
        "total": len(samples),
        "with_keyfinder": len(enriched),
        "successes": len(successes),
        "high_confidence_threshold": high_confidence,
        "review_flags_needed": len(action_items),
        "unchanged_final_decisions": True,
        "by_decision": count_items(successes, "decision"),
        "by_action": count_items(successes, "action"),
        "by_library": count_items(action_items, "library_id"),
        "by_type": count_items(action_items, "type"),
        "examples": action_items[:max(0, max_examples)],
        "items": action_items,
    }


def keyfinder_review_policy_item(sample: dict[str, Any], high_confidence: float = 0.75) -> dict[str, Any]:
    comparison = keyfinder_comparison_item(sample)
    confidence = comparison.get("confidence")
    try:
        confidence_value = float(confidence or 0.0)
    except (TypeError, ValueError):
        confidence_value = 0.0
    action = "none"
    reason = None
    if comparison["status"] == "success" and comparison["decision"] == "key_and_root_disagree" and confidence_value >= high_confidence:
        action = "add_review"
        reason = "keyfinder_high_confidence_disagreement"
    return {
        "name": comparison.get("name"),
        "library_id": comparison.get("library_id"),
        "library_name": comparison.get("library_name"),
        "relative_path": comparison.get("relative_path"),
        "type": comparison.get("type"),
        "confidence": confidence,
        "stored_key": comparison.get("stored_key"),
        "stored_root": comparison.get("stored_root"),
        "keyfinder_key": comparison.get("keyfinder_key"),
        "keyfinder_root": comparison.get("keyfinder_root"),
        "has_keyfinder": comparison.get("has_keyfinder"),
        "status": comparison.get("status"),
        "decision": comparison.get("decision"),
        "action": action,
        "reason": reason,
    }


def apply_keyfinder_review_policy(
    index_path: Path,
    records: list[dict[str, Any]],
    high_confidence: float = 0.75,
    dry_run: bool = False,
    write_every: int = 100,
    export_json: bool = True,
    max_examples: int = 20,
) -> dict[str, Any]:
    report = build_keyfinder_review_policy_report(records, high_confidence=high_confidence, max_examples=max_examples)
    report["dry_run"] = dry_run
    report["updated"] = 0
    if dry_run or not report["items"]:
        return report

    index = open_writable_index(index_path)
    try:
        for record in records:
            sample = _flatten_sample(record)
            item = keyfinder_review_policy_item(sample, high_confidence)
            if item["action"] != "add_review":
                continue
            updated_record = record_with_keyfinder_review_policy(record, item, high_confidence)
            upsert_record(index, updated_record)
            report["updated"] += 1
            if report["updated"] % max(1, write_every) == 0:
                index.write()
        index.write()
        if export_json and isinstance(index, SQLiteMetadataIndex):
            index.export_json(index_path.with_suffix(".json"))
    finally:
        close_index(index)
    return report


def record_with_keyfinder_review_policy(record: dict[str, Any], item: dict[str, Any], high_confidence: float) -> dict[str, Any]:
    updated = json.loads(json.dumps(record))
    analysis = dict(updated.get("analysis") or {})
    review = dict(analysis.get("review") or {})
    reasons = list(review.get("reasons") or [])
    reason = item.get("reason")
    if reason and reason not in reasons:
        reasons.append(reason)
    review["needs_review"] = True
    review["reasons"] = reasons

    external = dict(analysis.get("external") or {})
    keyfinder = dict(external.get("keyfinder") or {})
    keyfinder["policy"] = {
        "mode": "review_only",
        "action": item.get("action"),
        "reason": reason,
        "decision": item.get("decision"),
        "high_confidence_threshold": high_confidence,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    external["keyfinder"] = keyfinder
    analysis["external"] = external
    analysis["review"] = review
    updated["analysis"] = analysis
    return updated


def classification_audit_item(sample: dict[str, Any]) -> dict[str, Any]:
    relative_path = sample.get("relative_path") or ""
    file_path = sample.get("file_path") or ""
    name = sample.get("name") or Path(str(file_path)).name
    stored_category = sample.get("category") or "Unknown"
    stored_type = sample.get("type") or "Unknown"
    stem_text = normalized_audit_text(Path(str(name)).stem)
    folder_text = normalized_audit_text(" ".join(Path(str(relative_path or file_path)).parts[:-1]))
    reasons: list[str] = []
    suggested_category: str | None = None
    suggested_type: str | None = None

    if audit_text_has(stem_text, "fullmix") or audit_text_has(stem_text, "full mix"):
        reasons.append("ignored_fullmix_present")
    if audit_text_has(stem_text, "musicloop") or audit_text_has(stem_text, "music loop"):
        reasons.append("ignored_musicloop_present")

    loop_score = audit_score(stem_text, folder_text, AUDIT_LOOP_TOKENS)
    oneshot_score = audit_score(stem_text, folder_text, AUDIT_ONESHOT_TOKENS)
    if loop_score > oneshot_score:
        suggested_category = "Loops"
    elif oneshot_score > loop_score:
        suggested_category = "OneShots"
    if suggested_category and stored_category != suggested_category:
        reasons.append("category_mismatch_from_filename")

    drum_loop_score = audit_score(stem_text, "", AUDIT_DRUM_LOOP_TOKENS)
    if (suggested_category == "Loops" or stored_category == "Loops") and drum_loop_score > 0:
        suggested_type = "DrumLoops"
        if stored_type != "DrumLoops":
            reasons.append("drum_loop_misclassified")

    hinted_type, hint_score = best_audit_type_hint(stem_text, folder_text)
    if hinted_type and (suggested_category != "Loops" or suggested_type != "DrumLoops"):
        suggested_type = type_for_category(suggested_category or stored_category, hinted_type)
        if suggested_type != stored_type:
            reasons.append("type_mismatch_from_filename")

    folder_type, folder_score = best_audit_type_hint("", folder_text)
    filename_type, filename_score = best_audit_type_hint(stem_text, "")
    if filename_type and folder_type and filename_type != folder_type and filename_score >= 4 and folder_score > 0:
        reasons.append("filename_folder_type_conflict")

    return {
        "name": name,
        "library_id": sample.get("library_id") or "unknown",
        "library_name": sample.get("library_name"),
        "relative_path": relative_path,
        "file_path": file_path,
        "path_family": path_family(relative_path or file_path),
        "stored_category": stored_category,
        "stored_type": stored_type,
        "suggested_category": suggested_category,
        "suggested_type": suggested_type,
        "confidence": sample.get("confidence"),
        "duration": sample.get("duration"),
        "reasons": reasons,
    }


def type_for_category(category: str, hinted_type: str) -> str:
    if category == "Loops":
        return AUDIT_TYPE_TO_LOOP_TYPE.get(hinted_type, "MelodyLoops")
    return hinted_type


def best_audit_type_hint(stem_text: str, folder_text: str) -> tuple[str | None, int]:
    best_type: str | None = None
    best_score = 0
    for sample_type, patterns in AUDIT_TYPE_HINTS:
        score = audit_score(stem_text, folder_text, patterns)
        if score > best_score:
            best_type = sample_type
            best_score = score
    return best_type, best_score


def audit_score(stem_text: str, folder_text: str, patterns: tuple[str, ...]) -> int:
    stem_tokens = set(stem_text.split())
    folder_tokens = set(folder_text.split())
    score = 0
    for pattern in patterns:
        if audit_matches(stem_text, stem_tokens, pattern):
            score += 4
        if audit_matches(folder_text, folder_tokens, pattern):
            score += 1
    return score


def audit_matches(text: str, tokens: set[str], pattern: str) -> bool:
    pattern = normalized_audit_text(pattern)
    if not pattern:
        return False
    if " " in pattern:
        return pattern in text
    return pattern in tokens


def audit_text_has(text: str, pattern: str) -> bool:
    return audit_matches(text, set(text.split()), pattern)


def normalized_audit_text(value: str) -> str:
    return " ".join(Path(value).as_posix().replace("_", " ").replace("-", " ").replace(".", " ").replace("(", " ").replace(")", " ").lower().split())


def count_reason_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(reason for item in items for reason in item.get("reasons", []))
    return [{"value": value, "count": count} for value, count in counts.most_common()]


def keyfinder_comparison_item(sample: dict[str, Any]) -> dict[str, Any]:
    external = keyfinder_external(sample)
    confidence = sample.get("confidence")
    item = {
        "name": sample.get("name"),
        "library_id": sample.get("library_id") or "unknown",
        "library_name": sample.get("library_name"),
        "relative_path": sample.get("relative_path"),
        "type": sample.get("type") or "Unknown",
        "confidence": confidence,
        "confidence_bucket": confidence_bucket(confidence),
        "stored_key": sample.get("key"),
        "stored_root": sample.get("root_note"),
        "has_keyfinder": bool(external),
        "status": "missing",
        "keyfinder_key": None,
        "keyfinder_root": None,
        "matches_stored_key": False,
        "matches_stored_root": False,
        "conversion_used": False,
        "decision": "missing_keyfinder",
        "error": None,
    }
    if not external:
        return item
    item["status"] = external.get("status") or "unknown"
    item["keyfinder_key"] = external.get("normalized_key")
    item["keyfinder_root"] = external.get("root_note")
    item["conversion_used"] = bool(external.get("conversion_used"))
    item["error"] = external.get("error")
    item["matches_stored_key"] = bool(external.get("matches_stored_key")) or keys_match(item["keyfinder_key"], item["stored_key"])
    item["matches_stored_root"] = bool(external.get("matches_stored_root")) or roots_match(item["keyfinder_root"], item["stored_root"])
    item["decision"] = keyfinder_comparison_decision(item)
    return item


def keyfinder_external(sample: dict[str, Any]) -> dict[str, Any]:
    structured = sample.get("structured") or {}
    analysis = structured.get("analysis") if isinstance(structured, dict) else None
    if isinstance(analysis, dict):
        external = analysis.get("external") or {}
        keyfinder = external.get("keyfinder") if isinstance(external, dict) else None
        if isinstance(keyfinder, dict):
            return keyfinder
    flat_analysis = sample.get("analysis")
    if isinstance(flat_analysis, dict):
        external = flat_analysis.get("external") or {}
        keyfinder = external.get("keyfinder") if isinstance(external, dict) else None
        if isinstance(keyfinder, dict):
            return keyfinder
    return {}


def keyfinder_comparison_decision(item: dict[str, Any]) -> str:
    if not item.get("has_keyfinder"):
        return "missing_keyfinder"
    if item.get("status") != "success":
        return "keyfinder_error"
    if item.get("matches_stored_key"):
        return "key_match"
    if item.get("matches_stored_root"):
        return "root_match_key_diff"
    if not item.get("stored_key") and not item.get("stored_root"):
        return "no_stored_key"
    return "key_and_root_disagree"


def aggregate_keyfinder_group(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item.get(key) or "unknown"), []).append(item)
    rows = []
    for value, group in grouped.items():
        successes = [item for item in group if item["status"] == "success"]
        rows.append({
            "value": value,
            "count": len(group),
            "successes": len(successes),
            "errors": len(group) - len(successes),
            "conversion_used": sum(1 for item in group if item["conversion_used"]),
            "matches_stored_key": sum(1 for item in successes if item["matches_stored_key"]),
            "matches_stored_root": sum(1 for item in successes if item["matches_stored_root"]),
            "key_and_root_disagreements": sum(1 for item in successes if item["decision"] == "key_and_root_disagree"),
        })
    rows.sort(key=lambda row: (-row["count"], row["value"]))
    return rows


def build_keyfinder_experiment_report(
    records: list[dict[str, Any]],
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
    limit: int = 0,
    timeout: float = 15.0,
    scope: str = "failures",
    low_confidence: float = 0.35,
    convert_retry: bool = False,
) -> dict[str, Any]:
    command = shutil.which("keyfinder-cli") or shutil.which("keyfinder")
    ffmpeg_command = shutil.which("ffmpeg") if convert_retry else None
    targets = keyfinder_targets(records, scope=scope, low_confidence=low_confidence)
    if limit > 0:
        targets = targets[:limit]
    report: dict[str, Any] = {
        "backend": "keyfinder",
        "scope": scope,
        "command": command,
        "convert_retry": convert_retry,
        "ffmpeg_command": ffmpeg_command,
        "selected": len(targets),
        "processed": 0,
        "successes": 0,
        "conversion_attempts": 0,
        "conversion_successes": 0,
        "conversion_errors": 0,
        "missing_audio": 0,
        "errors": 0,
        "matches_stored_key": 0,
        "matches_stored_root": 0,
        "results": [],
    }
    if not command:
        report["errors"] = len(targets)
        report["backend_error"] = "keyfinder_not_found"
        return report

    for target in targets:
        playable = Path(_playable_path(target, library_roots, destination_roots))
        result = {
            "name": target.get("name"),
            "library_id": target.get("library_id"),
            "relative_path": target.get("relative_path"),
            "path": str(playable),
            "stored_key": target.get("key"),
            "stored_root": target.get("root_note"),
            "confidence": target.get("confidence"),
            "needs_review": target.get("needs_review"),
            "path_family": target.get("path_family") or path_family(target.get("relative_path") or target.get("file_path")),
        }
        if not playable.exists():
            result["status"] = "missing_audio"
            result["error"] = "audio_not_found"
            report["missing_audio"] += 1
            report["results"].append(result)
            continue
        keyfinder_result = run_keyfinder(command, playable, timeout=timeout)
        if keyfinder_result["status"] != "success" and convert_retry:
            report["conversion_attempts"] += 1
            retry_result = run_keyfinder_with_converted_wav(command, playable, ffmpeg_command, timeout=timeout)
            if retry_result.get("conversion_status") == "success":
                report["conversion_successes"] += 1
            else:
                report["conversion_errors"] += 1
            if retry_result["status"] == "success":
                keyfinder_result = retry_result
            else:
                keyfinder_result["conversion_status"] = retry_result.get("conversion_status")
                keyfinder_result["conversion_error"] = retry_result.get("conversion_error")
        result.update(keyfinder_result)
        if keyfinder_result["status"] == "success":
            report["processed"] += 1
            report["successes"] += 1
            if keys_match(result.get("normalized_key"), result.get("stored_key")):
                result["matches_stored_key"] = True
                report["matches_stored_key"] += 1
            else:
                result["matches_stored_key"] = False
            if roots_match(result.get("root_note"), result.get("stored_root")):
                result["matches_stored_root"] = True
                report["matches_stored_root"] += 1
            else:
                result["matches_stored_root"] = False
        else:
            report["errors"] += 1
        report["results"].append(result)
    report["error_reasons"] = count_items([item for item in report["results"] if item.get("status") != "success"], "error")
    report["success_by_path_family"] = count_items([item for item in report["results"] if item.get("status") == "success"], "path_family")
    report["error_by_path_family"] = count_items([item for item in report["results"] if item.get("status") != "success"], "path_family")
    return report


def enrich_keyfinder_metadata(
    index_path: Path,
    records: list[dict[str, Any]],
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
    limit: int = 0,
    timeout: float = 15.0,
    scope: str = "failures",
    low_confidence: float = 0.35,
    convert_retry: bool = False,
    keyfinder_workers: int = 1,
    dry_run: bool = False,
    write_every: int = 25,
    export_json: bool = True,
) -> dict[str, Any]:
    try:
        from tqdm import tqdm
    except ModuleNotFoundError:
        tqdm = None

    command = shutil.which("keyfinder-cli") or shutil.which("keyfinder")
    ffmpeg_command = shutil.which("ffmpeg") if convert_retry else None
    targets = keyfinder_targets(records, scope=scope, low_confidence=low_confidence)
    if limit > 0:
        targets = targets[:limit]
    report: dict[str, Any] = {
        "backend": "keyfinder",
        "mode": "metadata_enrichment",
        "scope": scope,
        "command": command,
        "convert_retry": convert_retry,
        "ffmpeg_command": ffmpeg_command,
        "selected": len(targets),
        "processed": 0,
        "successes": 0,
        "updated": 0,
        "conversion_attempts": 0,
        "conversion_successes": 0,
        "conversion_errors": 0,
        "missing_audio": 0,
        "errors": 0,
        "matches_stored_key": 0,
        "matches_stored_root": 0,
        "dry_run": dry_run,
        "results": [],
    }
    if not command:
        report["errors"] = len(targets)
        report["backend_error"] = "keyfinder_not_found"
        return report

    index = None if dry_run else open_writable_index(index_path)
    try:
        workers = max(1, int(keyfinder_workers))

        def run_for(playable_path: Path) -> tuple[dict[str, Any], bool]:
            direct = run_keyfinder(command, playable_path, timeout=timeout)
            if direct.get("status") == "success" or not convert_retry:
                return direct, False
            retry = run_keyfinder_with_converted_wav(command, playable_path, ffmpeg_command, timeout=timeout)
            if retry.get("status") == "success":
                return retry, True
            direct["conversion_status"] = retry.get("conversion_status")
            direct["conversion_error"] = retry.get("conversion_error")
            return direct, True

        # Pre-handle missing audio quickly, then parallelize only the runnable set.
        runnable: list[tuple[dict[str, Any], Path]] = []
        for target in targets:
            playable = Path(_playable_path(target, library_roots, destination_roots))
            if not playable.exists():
                missing = {
                    "name": target.get("name"),
                    "library_id": target.get("library_id"),
                    "relative_path": target.get("relative_path"),
                    "path": str(playable),
                    "stored_key": target.get("key"),
                    "stored_root": target.get("root_note"),
                    "confidence": target.get("confidence"),
                    "needs_review": target.get("needs_review"),
                    "path_family": target.get("path_family") or path_family(target.get("relative_path") or target.get("file_path")),
                    "status": "missing_audio",
                    "error": "audio_not_found",
                    "error_code": "audio_not_found",
                }
                report["missing_audio"] += 1
                report["results"].append(missing)
                continue
            runnable.append((target, playable))

        if workers <= 1:
            iterable = runnable
            if tqdm is not None:
                iterable = tqdm(runnable, total=len(runnable), unit="file", desc="KeyFinder")
            for target, playable in iterable:
                keyfinder_result, attempted = run_for(playable)
                _apply_keyfinder_result(
                    report,
                    index,
                    target,
                    playable,
                    keyfinder_result,
                    command,
                    scope,
                    write_every,
                    dry_run,
                    conversion_attempted=attempted,
                )
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                future_map = {pool.submit(run_for, playable): (target, playable) for target, playable in runnable}
                completed = as_completed(future_map)
                if tqdm is not None:
                    completed = tqdm(completed, total=len(future_map), unit="file", desc="KeyFinder")
                for fut in completed:
                    target, playable = future_map[fut]
                    try:
                        keyfinder_result, attempted = fut.result()
                    except Exception as exc:
                        keyfinder_result, attempted = ({"status": "error", "error": f"keyfinder_worker_error:{exc}", "raw_output": None}, False)
                    _apply_keyfinder_result(
                        report,
                        index,
                        target,
                        playable,
                        keyfinder_result,
                        command,
                        scope,
                        write_every,
                        dry_run,
                        conversion_attempted=attempted,
                    )
        if index:
            index.write()
            if export_json and isinstance(index, SQLiteMetadataIndex):
                index.export_json(index_path.with_suffix(".json"))
    finally:
        if index:
            close_index(index)
    report["error_reasons"] = count_items([item for item in report["results"] if item.get("status") != "success" or item.get("metadata_error")], "error")
    report["error_codes"] = count_items(
        [
            {
                **item,
                "error_code": item.get("error_code") or ("metadata_error" if item.get("metadata_error") else item.get("error")),
            }
            for item in report["results"]
            if item.get("status") != "success" or item.get("metadata_error")
        ],
        "error_code",
    )
    report["success_by_path_family"] = count_items([item for item in report["results"] if item.get("status") == "success"], "path_family")
    report["error_by_path_family"] = count_items([item for item in report["results"] if item.get("status") != "success"], "path_family")
    return report


def _apply_keyfinder_result(
    report: dict[str, Any],
    index: MetadataIndex | None,
    target: dict[str, Any],
    playable: Path,
    keyfinder_result: dict[str, Any],
    command: str,
    scope: str,
    write_every: int,
    dry_run: bool,
    *,
    conversion_attempted: bool,
) -> None:
    result: dict[str, Any] = {
        "name": target.get("name"),
        "library_id": target.get("library_id"),
        "relative_path": target.get("relative_path"),
        "path": str(playable),
        "stored_key": target.get("key"),
        "stored_root": target.get("root_note"),
        "confidence": target.get("confidence"),
        "needs_review": target.get("needs_review"),
        "path_family": target.get("path_family") or path_family(target.get("relative_path") or target.get("file_path")),
    }
    if conversion_attempted:
        report["conversion_attempts"] += 1
        if keyfinder_result.get("conversion_status") == "success":
            report["conversion_successes"] += 1
        else:
            report["conversion_errors"] += 1

    result.update(keyfinder_result)
    if keyfinder_result.get("status") == "success":
        report["processed"] += 1
        report["successes"] += 1
        result["matches_stored_key"] = keys_match(result.get("normalized_key"), result.get("stored_key"))
        result["matches_stored_root"] = roots_match(result.get("root_note"), result.get("stored_root"))
        if result["matches_stored_key"]:
            report["matches_stored_key"] += 1
        if result["matches_stored_root"]:
            report["matches_stored_root"] += 1
    else:
        report["errors"] += 1

    if not dry_run:
        structured = target.get("structured")
        if isinstance(structured, dict) and structured and index is not None:
            updated_record = record_with_keyfinder_external(structured, result, command, scope)
            upsert_record(index, updated_record)
            report["updated"] += 1
            if report["updated"] % max(1, write_every) == 0:
                index.write()
        else:
            report["errors"] += 1
            result["metadata_error"] = "missing_structured_record"

    report["results"].append(result)


def record_with_keyfinder_external(record: dict[str, Any], result: dict[str, Any], command: str | None, scope: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(record))
    analysis = dict(updated.get("analysis") or {})
    external = dict(analysis.get("external") or {})
    external["keyfinder"] = {
        "backend": "keyfinder",
        "scope": scope,
        "command": command,
        "status": result.get("status"),
        "raw_key": result.get("raw_key"),
        "normalized_key": result.get("normalized_key"),
        "root_note": result.get("root_note"),
        "raw_output": result.get("raw_output"),
        "error": result.get("error"),
        "matches_stored_key": result.get("matches_stored_key"),
        "matches_stored_root": result.get("matches_stored_root"),
        "stored_key": result.get("stored_key"),
        "stored_root": result.get("stored_root"),
        "path": result.get("path"),
        "conversion_used": result.get("conversion_status") == "success",
        "conversion_status": result.get("conversion_status"),
        "conversion_error": result.get("conversion_error"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    analysis["external"] = external
    updated["analysis"] = analysis
    return updated


def keyfinder_targets(records: list[dict[str, Any]], scope: str, low_confidence: float = 0.35) -> list[dict[str, Any]]:
    if scope == "failures":
        samples = [_flatten_sample(record) for record in records]
        failures = [sample for sample in samples if deep_review_failed(sample)]
        failures.sort(key=lambda sample: (sample.get("deep_review", {}).get("reason") or "unknown", sample.get("library_id") or "", sample.get("relative_path") or sample.get("name") or ""))
        return failures
    if scope == "review":
        return select_deep_review_candidates(records, low_confidence=low_confidence, retry_deep_failed=True)
    if scope == "all":
        samples = [_flatten_sample(record) for record in records]
        samples.sort(key=lambda sample: (sample.get("relative_path") or sample.get("file_path") or sample.get("name") or ""))
        return samples
    raise ValueError(f"Unknown KeyFinder scope: {scope}")


def deep_failure_item(sample: dict[str, Any]) -> dict[str, Any]:
    deep_review = sample.get("deep_review") or {}
    duration = sample.get("duration")
    return {
        "name": sample.get("name"),
        "library_id": sample.get("library_id"),
        "library_name": sample.get("library_name"),
        "relative_path": sample.get("relative_path"),
        "file_path": sample.get("file_path"),
        "path_family": path_family(sample.get("relative_path") or sample.get("file_path")),
        "format": sample.get("format") or Path(str(sample.get("file_path") or "")).suffix.lower().lstrip(".") or "unknown",
        "duration": duration,
        "duration_bucket": duration_bucket(duration),
        "type": sample.get("type") or "Unknown",
        "key": sample.get("key"),
        "root_note": sample.get("root_note"),
        "confidence": sample.get("confidence"),
        "reason": deep_review.get("reason") or "unknown",
        "attempts": deep_review.get("attempts") or 0,
        "last_attempt_at": deep_review.get("last_attempt_at"),
        "profile": deep_review.get("profile"),
        "engines": deep_review.get("engines") or [],
        "deep_review_path": deep_review.get("path"),
    }


def count_items(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts = Counter(str(item.get(key) or "unknown") for item in items)
    return [{"value": value, "count": count} for value, count in counts.most_common()]


def duration_bucket(duration: Any) -> str:
    if duration is None:
        return "unknown"
    try:
        value = float(duration)
    except (TypeError, ValueError):
        return "unknown"
    if value < 2:
        return "<2s"
    if value < 5:
        return "2-5s"
    if value < 10:
        return "5-10s"
    if value < 30:
        return "10-30s"
    return "30s+"


def confidence_bucket(confidence: Any) -> str:
    if confidence is None:
        return "unknown"
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return "unknown"
    if value < 0.35:
        return "<0.35"
    if value < 0.5:
        return "0.35-0.49"
    if value < 0.75:
        return "0.50-0.74"
    return "0.75+"


def path_family(path_value: Any, depth: int = 2) -> str:
    parts = [part for part in Path(str(path_value or "")).parts if part not in {"/", ""}]
    if not parts:
        return "unknown"
    if Path(parts[-1]).suffix:
        parts = parts[:-1]
    if not parts:
        return "unknown"
    if parts[0] == "Users" and len(parts) > 5:
        for marker in ("Indian Melodic", "Indian Percussion", "SAMPLES", "Key", "Unsorted"):
            if marker in parts:
                marker_index = parts.index(marker)
                parts = parts[marker_index:] if marker.startswith("Indian ") else parts[marker_index + 1 :]
                break
    if len(parts) <= 1:
        return parts[0]
    return " / ".join(parts[:depth])


def deep_failure_triage_hints(failures: list[dict[str, Any]]) -> list[str]:
    if not failures:
        return ["No deep-review failures are currently recorded."]
    hints: list[str] = []
    formats = {item.get("format") for item in failures}
    reasons = {item.get("reason") for item in failures}
    profiles = {item.get("profile") for item in failures}
    engine_sets = {tuple(item.get("engines") or []) for item in failures}
    duration_buckets = {item.get("duration_bucket") for item in failures}
    if len(formats) == 1:
        hints.append(f"All failures are {next(iter(formats))} files, so this does not look like broad unsupported-format handling.")
    if reasons == {"worker_crash:worker_crash"}:
        hints.append("All failures crashed both the primary worker and fallback worker; treat these as backend stability cases.")
    if duration_buckets and duration_buckets <= {"<2s", "2-5s", "5-10s"}:
        hints.append("Failures are all under 10 seconds, so short melodic phrases should be tested separately from long loops.")
    if profiles == {"deep"} and engine_sets == {("librosa", "essentia")}:
        hints.append("Failures happened under the deep librosa+essentia path; next backend test should compare fast/librosa-only or an external harmonic engine.")
    return hints


def run_keyfinder(command: str, path: Path, timeout: float = 15.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [command, str(path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "timeout", "raw_output": ""}
    except OSError as exc:
        return {"status": "error", "error": str(exc), "raw_output": ""}
    raw_output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if completed.returncode != 0:
        error = raw_output or f"exit_{completed.returncode}"
        return {
            "status": "error",
            "error": error,
            "error_code": normalize_keyfinder_error(error),
            "raw_output": raw_output,
        }
    raw_key = raw_output.splitlines()[0].strip() if raw_output else ""
    normalized_key, root_note = normalize_keyfinder_key(raw_key)
    return {
        "status": "success" if raw_key else "error",
        "raw_key": raw_key or None,
        "normalized_key": normalized_key,
        "root_note": root_note,
        "raw_output": raw_output,
        "error": None if raw_key else "empty_output",
        "error_code": None if raw_key else "empty_output",
    }


def run_keyfinder_with_converted_wav(command: str, path: Path, ffmpeg_command: str | None, timeout: float = 15.0) -> dict[str, Any]:
    if not ffmpeg_command:
        return {
            "status": "error",
            "error": "ffmpeg_not_found",
            "error_code": "ffmpeg_not_found",
            "raw_output": "",
            "conversion_status": "error",
            "conversion_error": "ffmpeg_not_found",
        }
    with tempfile.TemporaryDirectory(prefix="sample-key-indexer-keyfinder-") as temp_dir:
        converted = Path(temp_dir) / f"{path.stem}.keyfinder.wav"
        conversion = convert_to_pcm16_wav(ffmpeg_command, path, converted, timeout=timeout)
        if conversion["status"] != "success":
            return {
                "status": "error",
                "error": conversion["error"],
                "error_code": normalize_keyfinder_error(conversion["error"]),
                "raw_output": conversion.get("raw_output", ""),
                "conversion_status": "error",
                "conversion_error": conversion["error"],
            }
        result = run_keyfinder(command, converted, timeout=timeout)
        result["conversion_status"] = "success"
        result["conversion_error"] = None
        result["converted_path"] = str(converted)
        return result


def convert_to_pcm16_wav(ffmpeg_command: str, source: Path, destination: Path, timeout: float = 15.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                ffmpeg_command,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vn",
                "-acodec",
                "pcm_s16le",
                str(destination),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "ffmpeg_timeout", "raw_output": ""}
    except OSError as exc:
        return {"status": "error", "error": str(exc), "raw_output": ""}
    raw_output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if completed.returncode != 0:
        return {"status": "error", "error": raw_output or f"ffmpeg_exit_{completed.returncode}", "raw_output": raw_output}
    if not destination.exists():
        return {"status": "error", "error": "converted_file_missing", "raw_output": raw_output}
    return {"status": "success", "error": None, "raw_output": raw_output}


def normalize_keyfinder_error(error: str | None) -> str:
    text = (error or "").strip().lower()
    if not text:
        return "unknown_error"
    if "file doesn't exist or unhandle format" in text or "unable to open audio file" in text:
        return "audio_unopenable_or_unhandled"
    if "does not have any audio streams" in text:
        return "no_audio_streams"
    if "unable to resample audio into 16bit pcm data" in text:
        return "pcm16_resample_failed"
    if "ffmpeg_not_found" in text:
        return "ffmpeg_not_found"
    if "timeout" in text:
        return "timeout"
    if text.startswith("exit_"):
        return "keyfinder_exit_error"
    if text.startswith("ffmpeg_exit_"):
        return "ffmpeg_exit_error"
    return text[:120]


def normalize_keyfinder_key(raw_key: str | None) -> tuple[str | None, str | None]:
    value = (raw_key or "").strip()
    if not value:
        return None, None
    value = value.replace("♭", "b").replace("♯", "#")
    if value.lower().endswith(" minor"):
        root = value[:-6].strip()
        mode = "minor"
    elif value.lower().endswith(" major"):
        root = value[:-6].strip()
        mode = "major"
    elif value.endswith("m") and len(value) > 1:
        root = value[:-1]
        mode = "minor"
    else:
        root = value
        mode = "major"
    root = FLAT_TO_SHARP.get(root, root)
    return f"{root}_{mode}", root


def keys_match(detected_key: Any, stored_key: Any) -> bool:
    if not detected_key or not stored_key:
        return False
    detected = str(detected_key)
    stored = str(stored_key)
    if "_" not in stored:
        return detected.startswith(f"{stored}_")
    return detected == stored


def roots_match(detected_root: Any, stored_root: Any) -> bool:
    if not detected_root or not stored_root:
        return False
    return str(detected_root) == str(stored_root)


def discover_deep_backends() -> dict[str, Any]:
    return {
        "commands": [discover_command_backend(spec) for spec in DEEP_BACKEND_COMMANDS],
        "qm_vamp_plugins": discover_qm_vamp_plugins(),
    }


def discover_command_backend(spec: dict[str, Any]) -> dict[str, Any]:
    for command in spec["commands"]:
        path = shutil.which(command)
        if path:
            return {
                "id": spec["id"],
                "label": spec["label"],
                "status": "available",
                "command": command,
                "path": path,
                "version": command_version(path, spec["version_args"]),
                "purpose": spec["purpose"],
                "required": bool(spec.get("required")),
            }
    return {
        "id": spec["id"],
        "label": spec["label"],
        "status": "missing",
        "command": None,
        "path": None,
        "version": None,
        "purpose": spec["purpose"],
        "required": bool(spec.get("required")),
    }


def command_version(path: str, version_args: tuple[str, ...]) -> str | None:
    try:
        completed = subprocess.run(
            [path, *version_args],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    return output.splitlines()[0] if output else None


def discover_qm_vamp_plugins() -> dict[str, Any]:
    matches: list[str] = []
    searched: list[str] = []
    for plugin_dir in VAMP_PLUGIN_DIRS:
        searched.append(str(plugin_dir))
        if not plugin_dir.exists():
            continue
        for path in plugin_dir.iterdir():
            if "qm" in path.name.lower():
                matches.append(str(path))
    return {
        "status": "available" if matches else "missing",
        "matches": sorted(matches),
        "searched": searched,
    }


def format_deep_failure_report(report: dict[str, Any]) -> str:
    lines = [f"Deep review failures: {report['total']} files"]
    for title, key in (
        ("Reasons", "by_reason"),
        ("Libraries", "by_library"),
        ("Formats", "by_format"),
        ("Types", "by_type"),
        ("Durations", "by_duration"),
        ("Path families", "by_path_family"),
    ):
        if not report[key]:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for item in report[key]:
            lines.append(f"- {item['value']}: {item['count']}")
    if report.get("triage_hints"):
        lines.append("")
        lines.append("Triage hints:")
        for hint in report["triage_hints"]:
            lines.append(f"- {hint}")
    if report["examples"]:
        lines.append("")
        lines.append("Examples:")
        for item in report["examples"]:
            lines.append(f"- {item['name']} | {item['reason']} | {item['duration_bucket']} | attempts {item['attempts']}")
    return "\n".join(lines)


def format_backend_check_report(report: dict[str, Any]) -> str:
    targets = report["deep_failure_targets"]
    status = report["backend_status"]
    lines = [
        "Deep backend check:",
        f"  Deep-review failure targets: {targets['total']} files",
    ]
    for title, key in (
        ("Failure reasons", "by_reason"),
        ("Failure formats", "by_format"),
        ("Failure durations", "by_duration"),
        ("Failure path families", "by_path_family"),
    ):
        if not targets[key]:
            continue
        lines.append(f"  {title}:")
        for item in targets[key]:
            lines.append(f"    - {item['value']}: {item['count']}")
    if targets.get("triage_hints"):
        lines.append("  Triage hints:")
        for hint in targets["triage_hints"]:
            lines.append(f"    - {hint}")
    lines.append("")
    lines.append("Candidate backends:")
    for backend in status["commands"]:
        detail = backend["path"] if backend["status"] == "available" else "not found on PATH"
        requirement = "required" if backend.get("required") else "optional"
        lines.append(f"- {backend['label']}: {backend['status']} ({detail}) [{requirement}]")
        if backend.get("version"):
            lines.append(f"  Version: {backend['version']}")
        lines.append(f"  Role: {backend['purpose']}")
    if report.get("missing_required_backends"):
        lines.append("")
        lines.append("Missing required backends:")
        for backend in report["missing_required_backends"]:
            commands = ", ".join(next((spec["commands"] for spec in DEEP_BACKEND_COMMANDS if spec["id"] == backend["id"]), (backend["label"],)))
            lines.append(f"- {backend['label']} ({commands})")
    qm_plugins = status["qm_vamp_plugins"]
    lines.append(f"- QM Vamp Plugins: {qm_plugins['status']}")
    if qm_plugins["matches"]:
        for match in qm_plugins["matches"][:10]:
            lines.append(f"  - {match}")
    else:
        lines.append("  No qm-named Vamp plugin files found in the standard macOS/Homebrew Vamp paths.")
    lines.append("")
    lines.append("Next experiment:")
    lines.append("- Use KeyFinder CLI as the required external key-comparison backend.")
    lines.append("- If Sonic Annotator and QM Vamp Plugins are available, test them later against the recorded deep failures.")
    lines.append("- Keep aubio optional for tempo/onset checks rather than primary key detection.")
    return "\n".join(lines)


def format_keyfinder_comparison_report(report: dict[str, Any]) -> str:
    lines = [
        "KeyFinder comparison:",
        f"  Total samples: {report['total']} files",
        f"  With KeyFinder metadata: {report['enriched']} files",
        f"  Missing KeyFinder metadata: {report['missing_keyfinder']} files",
        f"  Successes: {report['successes']} files",
        f"  Errors: {report['errors']} files",
        f"  Conversion used: {report['conversion_used']} files",
        f"  Matches stored key: {report['matches_stored_key']} files",
        f"  Matches stored root: {report['matches_stored_root']} files",
        f"  Root-only matches: {report['root_only_matches']} files",
        f"  Key/root disagreements: {report['key_and_root_disagreements']} files",
    ]
    for title, key in (
        ("By decision", "by_decision"),
        ("By library", "by_library"),
        ("By type", "by_type"),
        ("By confidence", "by_confidence"),
        ("By status", "by_status"),
    ):
        rows = report.get(key) or []
        if not rows:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for row in rows[:12]:
            if "successes" in row:
                lines.append(
                    f"- {row['value']}: {row['count']} files | success {row['successes']} | "
                    f"key match {row['matches_stored_key']} | root match {row['matches_stored_root']} | "
                    f"disagree {row['key_and_root_disagreements']} | converted {row['conversion_used']}"
                )
            else:
                lines.append(f"- {row['value']}: {row['count']}")
    if report.get("disagreement_examples"):
        lines.append("")
        lines.append("High-confidence disagreement examples:")
        for item in report["disagreement_examples"][:10]:
            lines.append(
                f"- {item['name']} | {item['library_id']} | confidence {item['confidence']} | "
                f"stored {item.get('stored_key') or item.get('stored_root')} | KeyFinder {item.get('keyfinder_key') or item.get('keyfinder_root')}"
            )
    if report.get("missing_examples"):
        lines.append("")
        lines.append("Missing metadata examples:")
        for item in report["missing_examples"][:5]:
            lines.append(f"- {item['name']} | {item['library_id']} | {item.get('relative_path')}")
    return "\n".join(lines)


def format_classification_audit_report(report: dict[str, Any]) -> str:
    lines = [
        "Classification audit:",
        f"  Total samples: {report['total']} files",
        f"  Suspicious classifications: {report['suspicious']} files",
    ]
    for title, key in (
        ("Reasons", "by_reason"),
        ("Libraries", "by_library"),
        ("Stored types", "by_type"),
        ("Path families", "by_path_family"),
    ):
        rows = report.get(key) or []
        if not rows:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for row in rows[:12]:
            lines.append(f"- {row['value']}: {row['count']}")
    if report.get("examples"):
        lines.append("")
        lines.append("Examples:")
        for item in report["examples"][:20]:
            suggestion = item.get("suggested_type") or item.get("suggested_category") or "review"
            reasons = ", ".join(item.get("reasons") or [])
            lines.append(
                f"- {item['name']} | stored {item['stored_category']}/{item['stored_type']} | "
                f"suggested {item.get('suggested_category') or '?'} / {suggestion} | {reasons}"
            )
    return "\n".join(lines)


def format_keyfinder_review_policy_report(report: dict[str, Any]) -> str:
    lines = [
        "KeyFinder review policy:",
        f"  Mode: {report['mode']}",
        f"  Total samples: {report['total']} files",
        f"  With KeyFinder metadata: {report['with_keyfinder']} files",
        f"  Successful KeyFinder results: {report['successes']} files",
        f"  High-confidence threshold: {report['high_confidence_threshold']}",
        f"  Review flags needed: {report['review_flags_needed']} files",
        f"  Metadata updated: {report.get('updated', 0)} files",
        "  Final key/root/confidence/routing changed: no",
    ]
    if report.get("dry_run"):
        lines.append("  Dry run: no metadata was changed")
    for title, key in (
        ("By decision", "by_decision"),
        ("By action", "by_action"),
        ("Review libraries", "by_library"),
        ("Review types", "by_type"),
    ):
        rows = report.get(key) or []
        if not rows:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for row in rows[:12]:
            lines.append(f"- {row['value']}: {row['count']}")
    if report.get("examples"):
        lines.append("")
        lines.append("Review flag examples:")
        for item in report["examples"][:20]:
            lines.append(
                f"- {item['name']} | confidence {item['confidence']} | stored {item.get('stored_key') or item.get('stored_root')} | "
                f"KeyFinder {item.get('keyfinder_key') or item.get('keyfinder_root')} | {item.get('reason')}"
            )
    return "\n".join(lines)


def format_keyfinder_experiment_report(report: dict[str, Any]) -> str:
    is_enrichment = report.get("mode") == "metadata_enrichment"
    lines = [
        "KeyFinder metadata enrichment:" if is_enrichment else "KeyFinder experiment:",
        f"  Scope: {report.get('scope') or 'failures'}",
        f"  Command: {report.get('command') or 'not found'}",
        f"  Conversion retry: {'on' if report.get('convert_retry') else 'off'}",
        f"  ffmpeg: {report.get('ffmpeg_command') or 'not used'}",
        f"  Selected samples: {report['selected']} files",
        f"  Processed: {report['processed']} files",
        f"  Successes: {report['successes']} files",
        f"  Conversion attempts: {report.get('conversion_attempts', 0)} files",
        f"  Conversion successes: {report.get('conversion_successes', 0)} files",
        f"  Conversion errors: {report.get('conversion_errors', 0)} files",
        f"  Missing audio: {report['missing_audio']} files",
        f"  Errors: {report['errors']} files",
        f"  Matches stored key: {report['matches_stored_key']} files",
        f"  Matches stored root: {report['matches_stored_root']} files",
    ]
    if is_enrichment:
        lines.insert(8, f"  Metadata updated: {report.get('updated', 0)} files")
    if is_enrichment and report.get("dry_run"):
        lines.append("  Dry run: no metadata was changed")
    if report.get("backend_error"):
        lines.append(f"  Backend error: {report['backend_error']}")
    if report.get("error_reasons"):
        lines.append("")
        lines.append("Error reasons:")
        for item in report["error_reasons"][:10]:
            lines.append(f"- {item['value']}: {item['count']}")
    if report.get("error_codes"):
        lines.append("")
        lines.append("Normalized error codes:")
        for item in report["error_codes"][:10]:
            lines.append(f"- {item['value']}: {item['count']}")
    if report.get("success_by_path_family"):
        lines.append("")
        lines.append("Successes by path family:")
        for item in report["success_by_path_family"][:10]:
            lines.append(f"- {item['value']}: {item['count']}")
    if report.get("error_by_path_family"):
        lines.append("")
        lines.append("Errors by path family:")
        for item in report["error_by_path_family"][:10]:
            lines.append(f"- {item['value']}: {item['count']}")
    if report["results"]:
        lines.append("")
        lines.append("Results:")
        for item in report["results"][:20]:
            if item["status"] == "success":
                lines.append(
                    f"- {item['name']} | KeyFinder {item.get('raw_key')} ({item.get('normalized_key')}) | "
                    f"stored {item.get('stored_key') or item.get('stored_root')} | "
                    f"key match {item.get('matches_stored_key')} | root match {item.get('matches_stored_root')}"
                )
            else:
                lines.append(f"- {item['name']} | {item['status']} | {item.get('error')}")
    if report.get("selected") and report.get("processed") is not None:
        remaining = report["selected"] - report["processed"] - report["missing_audio"]
        if remaining < 0:
            remaining = 0
        lines.append("")
        lines.append(f"  Remaining without successful KeyFinder result: {remaining} files")
    return "\n".join(lines)


def write_deep_failure_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def write_keyfinder_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def write_catalog_health_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def write_classification_audit_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def write_classification_audit_csv(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "name",
        "library_id",
        "library_name",
        "relative_path",
        "file_path",
        "path_family",
        "stored_category",
        "stored_type",
        "suggested_category",
        "suggested_type",
        "confidence",
        "duration",
        "reasons",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in report["items"]:
            row = dict(item)
            row["reasons"] = ",".join(row.get("reasons") or [])
            writer.writerow({field: row.get(field) for field in fields})


def write_deep_failure_csv(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "name",
        "library_id",
        "library_name",
        "relative_path",
        "file_path",
        "path_family",
        "format",
        "duration",
        "duration_bucket",
        "type",
        "confidence",
        "reason",
        "attempts",
        "last_attempt_at",
        "profile",
        "engines",
        "deep_review_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in report["failures"]:
            row = dict(item)
            row["engines"] = ",".join(row.get("engines") or [])
            writer.writerow({field: row.get(field) for field in fields})


def format_review_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"Total samples: {summary['total']}",
        f"Needs review: {summary['needs_review']} ({summary['review_percentage']}%)",
    ]
    if summary["reasons"]:
        lines.append("")
        lines.append("Review reasons:")
        for item in summary["reasons"]:
            lines.append(f"- {item['reason']}: {item['count']}")
    if summary["types"]:
        lines.append("")
        lines.append("Review sample types:")
        for item in summary["types"]:
            lines.append(f"- {item['type']}: {item['count']}")
    if summary["examples"]:
        lines.append("")
        lines.append("Lowest-confidence review examples:")
        for item in summary["examples"]:
            reasons = ", ".join(item["reasons"]) or "unknown"
            lines.append(f"- {item['name']} | {item['key']} | confidence {item['confidence']} | {reasons}")
    return "\n".join(lines)


def build_catalog_health_report(
    records: list[dict[str, Any]],
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
    max_examples: int = 5,
) -> dict[str, Any]:
    samples = [_flatten_sample(record) for record in records]
    by_library: dict[str, dict[str, Any]] = {}
    totals = {"total": 0, "playable": 0, "missing": 0}
    missing_examples: list[dict[str, Any]] = []

    def bucket_for(sample: dict[str, Any]) -> dict[str, Any]:
        library_id = sample.get("library_id") or "unknown"
        item = by_library.get(library_id)
        if item is None:
            item = {
                "library_id": library_id,
                "library_name": sample.get("library_name") or library_id,
                "total": 0,
                "playable": 0,
                "missing": 0,
                "by_source": {},
                "missing_examples": [],
            }
            by_library[library_id] = item
        return item

    for sample in samples:
        info = _playback_info(sample, library_roots, destination_roots)
        status = info.get("status") or "missing"
        source = info.get("source") or "missing"
        bucket = bucket_for(sample)

        totals["total"] += 1
        bucket["total"] += 1
        bucket["by_source"][source] = int(bucket["by_source"].get(source, 0)) + 1

        if status == "available":
            totals["playable"] += 1
            bucket["playable"] += 1
        else:
            totals["missing"] += 1
            bucket["missing"] += 1
            example = {
                "library_id": bucket["library_id"],
                "library_name": bucket["library_name"],
                "name": sample.get("name"),
                "relative_path": sample.get("relative_path"),
                "path_family": sample.get("path_family"),
                "playback_path": info.get("path") or "",
                "playback_source": source,
            }
            if len(missing_examples) < max_examples:
                missing_examples.append(example)
            if len(bucket["missing_examples"]) < max_examples:
                bucket["missing_examples"].append(example)

    libraries = sorted(by_library.values(), key=lambda item: (item["missing"], item["library_id"]), reverse=True)
    for item in libraries:
        total = max(1, int(item["total"]))
        item["playable_pct"] = round((int(item["playable"]) / total) * 100, 2)
        item["missing_pct"] = round((int(item["missing"]) / total) * 100, 2)
        item["by_source"] = [
            {"value": key, "count": int(count)}
            for key, count in sorted(item["by_source"].items(), key=lambda kv: (-int(kv[1]), kv[0]))
        ]

    overall_total = max(1, totals["total"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            **totals,
            "playable_pct": round((totals["playable"] / overall_total) * 100, 2),
            "missing_pct": round((totals["missing"] / overall_total) * 100, 2),
        },
        "libraries": libraries,
        "missing_examples": missing_examples,
    }


def format_catalog_health_report(report: dict[str, Any]) -> str:
    totals = report.get("totals") or {}
    lines = [
        "Catalog health:",
        f"  Total samples: {totals.get('total', 0)}",
        f"  Playable: {totals.get('playable', 0)} ({totals.get('playable_pct', 0)}%)",
        f"  Missing: {totals.get('missing', 0)} ({totals.get('missing_pct', 0)}%)",
    ]
    lines.append("")
    lines.append("By library:")
    for lib in (report.get("libraries") or [])[:25]:
        lines.append(
            f"- {lib.get('library_id')} | {lib.get('library_name')} | total {lib.get('total')} | "
            f"playable {lib.get('playable')} ({lib.get('playable_pct')}%) | "
            f"missing {lib.get('missing')} ({lib.get('missing_pct')}%)"
        )
    examples = report.get("missing_examples") or []
    if examples:
        lines.append("")
        lines.append("Missing examples:")
        for item in examples[:5]:
            lines.append(
                f"- {item.get('library_id')} | {item.get('name')} | {item.get('playback_source')} | {item.get('playback_path')}"
            )
    return "\n".join(lines)


def format_deep_review_plan(plan: dict[str, Any]) -> str:
    lines = [
        f"Deep review candidates: {plan['selected']}",
        f"Low-confidence threshold: {plan['low_confidence']}",
    ]
    if plan.get("skipped_deep_failed"):
        lines.append(f"Skipped previous deep-review failures: {plan['skipped_deep_failed']}")
    if plan.get("retry_deep_failed"):
        lines.append("Retrying previous deep-review failures")
    if plan["reasons"]:
        lines.append("")
        lines.append("Selection reasons:")
        for item in plan["reasons"]:
            lines.append(f"- {item['reason']}: {item['count']}")
    if plan["examples"]:
        lines.append("")
        lines.append("Candidate examples:")
        for item in plan["examples"]:
            reasons = ", ".join(item["selection_reasons"]) or "selected"
            lines.append(f"- {item['name']} | {item['key']} | confidence {item['confidence']} | {reasons}")
    return "\n".join(lines)


def rerun_deep_review(
    index_path: Path,
    candidates: list[dict[str, Any]],
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
    analysis_duration: float = 30.0,
    sample_rate: int = 22050,
    analysis_profile: str = "deep",
    engines: tuple[str, ...] | None = None,
    dry_run: bool = False,
    write_every: int = 25,
    export_json: bool = True,
    isolated: bool = True,
) -> dict[str, Any]:
    summary = {
        "selected": len(candidates),
        "processed": 0,
        "missing": 0,
        "improved_confidence": 0,
        "still_needs_review": 0,
        "errors": 0,
        "worker_crashes": 0,
        "fallback_successes": 0,
        "marked_failed": 0,
        "dry_run": dry_run,
        "details": {
            "missing": [],
            "errors": [],
            "fallback_successes": [],
        },
    }
    if dry_run:
        return summary

    index = open_writable_index(index_path)
    try:
        selected_engines = normalize_engines(analysis_profile, engines)
        for candidate in candidates:
            playable_path = Path(_playable_path(candidate, library_roots, destination_roots))
            if not playable_path.exists() or not playable_path.is_file():
                summary["missing"] += 1
                add_summary_detail(summary, "missing", candidate, playable_path, "audio_not_found")
                continue
            result, worker_error = analyze_candidate(playable_path, analysis_duration, sample_rate, analysis_profile, selected_engines, isolated=isolated)
            if worker_error:
                summary["worker_crashes"] += 1
                fallback_result, fallback_error = analyze_candidate(playable_path, analysis_duration, sample_rate, "fast", ("librosa",), isolated=isolated)
                if fallback_error:
                    summary["worker_crashes"] += 1
                    summary["errors"] += 1
                    add_summary_detail(summary, "errors", candidate, playable_path, f"worker_crash:{fallback_error}")
                    mark_deep_review_failed(index, candidate, playable_path, f"worker_crash:{fallback_error}", analysis_profile, selected_engines)
                    summary["marked_failed"] += 1
                    continue
                result = fallback_result
                summary["fallback_successes"] += 1
                add_summary_detail(summary, "fallback_successes", candidate, playable_path, worker_error)
            result = preserve_candidate_context(result, candidate)
            if result.confidence > float(candidate.get("confidence") or 0.0):
                summary["improved_confidence"] += 1
            if result.needs_review:
                summary["still_needs_review"] += 1
            if result.error:
                summary["errors"] += 1
                add_summary_detail(summary, "errors", candidate, playable_path, result.error)
            index.upsert(result)
            summary["processed"] += 1
            if summary["processed"] % max(1, write_every) == 0:
                index.write()
        index.write()
        if export_json and isinstance(index, SQLiteMetadataIndex):
            index.export_json(index_path.with_suffix(".json"))
    finally:
        close_index(index)
    return summary


def analyze_candidate(
    path: Path,
    analysis_duration: float,
    sample_rate: int,
    analysis_profile: str,
    selected_engines: tuple[str, ...],
    isolated: bool = True,
):
    if not isolated:
        return analyze_file(path, analysis_duration, sample_rate, analysis_profile, selected_engines), None
    try:
        with ProcessPoolExecutor(max_workers=1) as pool:
            future = pool.submit(analyze_file, path, analysis_duration, sample_rate, analysis_profile, selected_engines)
            return future.result(), None
    except BrokenProcessPool:
        return None, "worker_crash"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def open_writable_index(index_path: Path):
    if index_path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        return SQLiteMetadataIndex(index_path)
    return MetadataIndex(index_path)


def close_index(index) -> None:
    close = getattr(index, "close", None)
    if close:
        close()


def preserve_candidate_context(result, candidate: dict[str, Any]):
    return replace(
        result,
        file_path=candidate.get("file_path") or result.file_path,
        relative_path=candidate.get("relative_path"),
        library_id=candidate.get("library_id"),
        library_name=candidate.get("library_name"),
        library_root=candidate.get("library_root"),
        destination=candidate.get("destination"),
    )


def add_summary_detail(summary: dict[str, Any], bucket: str, candidate: dict[str, Any], playable_path: Path, reason: str) -> None:
    details = summary.setdefault("details", {}).setdefault(bucket, [])
    details.append({
        "name": candidate.get("name"),
        "library_id": candidate.get("library_id"),
        "relative_path": candidate.get("relative_path"),
        "path": str(playable_path),
        "reason": reason,
    })


def mark_deep_review_failed(index, candidate: dict[str, Any], playable_path: Path, reason: str, analysis_profile: str, selected_engines: tuple[str, ...]) -> None:
    record = dict(candidate.get("structured") or {})
    if not record:
        return
    analysis = dict(record.get("analysis") or {})
    previous = analysis.get("deep_review") or {}
    attempts = int(previous.get("attempts") or 0) + 1
    analysis["deep_review"] = {
        "failed": True,
        "reason": reason,
        "attempts": attempts,
        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        "profile": analysis_profile,
        "engines": list(selected_engines),
        "path": str(playable_path),
    }
    record["analysis"] = analysis
    upsert_record(index, record)


def upsert_record(index, record: dict[str, Any]) -> None:
    if hasattr(index, "upsert_record"):
        index.upsert_record(record)
        return
    index.records[_record_path(record)] = record


def _record_path(record: dict[str, Any]) -> str:
    file_block = record.get("file")
    if isinstance(file_block, dict):
        return str(file_block.get("path", ""))
    return str(record.get("file_path", ""))


def format_deep_review_result(summary: dict[str, Any]) -> str:
    lines = [
        "Deep review rerun:",
        f"  Selected: {summary['selected']} files",
        f"  Processed: {summary['processed']} files",
        f"  Missing audio: {summary['missing']} files",
        f"  Improved confidence: {summary['improved_confidence']} files",
        f"  Still needs review: {summary['still_needs_review']} files",
        f"  Errors: {summary['errors']} files",
        f"  Worker crashes: {summary.get('worker_crashes', 0)} files",
        f"  Fallback successes: {summary.get('fallback_successes', 0)} files",
        f"  Marked failed: {summary.get('marked_failed', 0)} files",
    ]
    if summary.get("dry_run"):
        lines.append("  Dry run: no metadata was changed")
    for title, bucket in (
        ("Missing examples", "missing"),
        ("Error examples", "errors"),
        ("Fallback examples", "fallback_successes"),
    ):
        examples = (summary.get("details") or {}).get(bucket, [])[:5]
        if not examples:
            continue
        lines.append(f"  {title}:")
        for item in examples:
            lines.append(f"    - {item.get('name')} | {item.get('reason')}")
    return "\n".join(lines)


def write_deep_review_report(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize samples that need review from a metadata index.")
    parser.add_argument("index_path", type=Path, help="Path to metadata_index.json or metadata_index.sqlite.")
    parser.add_argument("--examples", type=int, default=10, help="Number of lowest-confidence review examples to print.")
    parser.add_argument("--catalog-health", action="store_true", help="Print playable vs missing summary for one or more libraries (requires mounted roots via --library-root/--destination-root).")
    parser.add_argument("--catalog-health-json", type=Path, default=None, help="Write the catalog health report to JSON.")
    parser.add_argument("--deep-plan", action="store_true", help="Print the V3.3 deep-review candidate plan.")
    parser.add_argument("--deep-rerun", action="store_true", help="Rerun analysis only for deep-review candidates and update the index.")
    parser.add_argument("--deep-failures", action="store_true", help="Print the V3.5 deep-review failure report.")
    parser.add_argument("--backend-check", action="store_true", help="Print the V3.6 optional deep-backend availability report.")
    parser.add_argument("--classification-audit", action="store_true", help="Print suspicious category/type classifications before rebuilding organised audio folders.")
    parser.add_argument("--keyfinder-compare", action="store_true", help="Compare stored analysis.external.keyfinder metadata against the current stored key/root decisions.")
    parser.add_argument("--keyfinder-apply-review", action="store_true", help="Apply the V3.6 KeyFinder review-only policy without changing final keys or routing.")
    parser.add_argument("--keyfinder-experiment", action="store_true", help="Run KeyFinder CLI against recorded deep-review failures without updating metadata.")
    parser.add_argument("--keyfinder-enrich", action="store_true", help="Run KeyFinder CLI and store its output under analysis.external.keyfinder without changing the main key decision.")
    parser.add_argument("--keyfinder-scope", choices=("failures", "review", "all"), default="failures", help="Samples to send to KeyFinder: failed deep-review records, review candidates, or the full index.")
    parser.add_argument("--keyfinder-convert-retry", action="store_true", help="Retry failed KeyFinder reads via a temporary ffmpeg 16-bit PCM WAV conversion.")
    parser.add_argument("--keyfinder-workers", type=int, default=1, help="Parallelism for KeyFinder enrich/experiment. Default: 1.")
    parser.add_argument("--dry-run", action="store_true", help="Preview deep-review rerun counts without updating metadata.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum deep-review candidates to select. 0 means no limit.")
    parser.add_argument("--low-confidence", type=float, default=0.35, help="Select records below this confidence for deep review.")
    parser.add_argument("--keyfinder-review-threshold", type=float, default=0.75, help="Minimum stored confidence for KeyFinder disagreement to add a review flag.")
    parser.add_argument("--retry-deep-failed", action="store_true", help="Include records already marked as failed by a previous deep-review rerun.")
    parser.add_argument("--library-root", action="append", default=[], help="Playback/source root override as LIBRARY_ID=/Volumes/USB/Samples. Can be passed more than once.")
    parser.add_argument("--destination-root", action="append", default=[], help="Organized Key/Unsorted root override as LIBRARY_ID=/Volumes/USB/SAMPLEZ. Can be passed more than once.")
    parser.add_argument("--analysis-duration", type=float, default=30.0, help="Max seconds loaded per rerun file.")
    parser.add_argument("--sample-rate", type=int, default=22050, help="Analysis sample rate for reruns.")
    parser.add_argument("--analysis-profile", choices=("fast", "balanced", "deep"), default="deep", help="Analysis depth preset for reruns.")
    parser.add_argument("--engines", default=None, help="Comma-separated analysis engines for reruns.")
    parser.add_argument("--write-every", type=int, default=25, help="Write metadata after this many rerun files.")
    parser.add_argument("--no-json-export", action="store_true", help="Do not export/update metadata_index.json after SQLite reruns.")
    parser.add_argument("--report-json", type=Path, default=None, help="Write a JSON rerun report with selected counts and failure examples.")
    parser.add_argument("--keyfinder-json", type=Path, default=None, help="Write the KeyFinder experiment report to JSON.")
    parser.add_argument("--classification-json", type=Path, default=None, help="Write the classification audit report to JSON.")
    parser.add_argument("--classification-csv", type=Path, default=None, help="Write suspicious classification items to CSV.")
    parser.add_argument("--failures-json", type=Path, default=None, help="Write the deep-review failure report to JSON.")
    parser.add_argument("--failures-csv", type=Path, default=None, help="Write the deep-review failure list to CSV.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index_path = args.index_path.expanduser().resolve()
    if not index_path.exists():
        print(f"Metadata index does not exist: {index_path}")
        return 2
    records = load_records(index_path)
    if args.catalog_health:
        try:
            library_roots = parse_library_roots(args.library_root)
            destination_roots = parse_library_roots(args.destination_root, option_name="--destination-root")
        except ValueError as exc:
            print(str(exc))
            return 2
        report = build_catalog_health_report(records, library_roots=library_roots, destination_roots=destination_roots, max_examples=max(0, args.examples))
        print(format_catalog_health_report(report))
        if args.catalog_health_json:
            report_path = args.catalog_health_json.expanduser().resolve()
            write_catalog_health_report(report, report_path)
            print(f"Catalog health JSON: {report_path}")
        return 0
    if args.backend_check:
        report = build_backend_check_report(records)
        print(format_backend_check_report(report))
        return 2 if report.get("missing_required_backends") else 0
    if args.keyfinder_compare:
        report = build_keyfinder_comparison_report(records, max_examples=max(0, args.examples))
        print(format_keyfinder_comparison_report(report))
        if args.keyfinder_json:
            report_path = args.keyfinder_json.expanduser().resolve()
            write_keyfinder_report(report, report_path)
            print(f"KeyFinder comparison JSON: {report_path}")
        return 0
    if args.keyfinder_apply_review:
        report = apply_keyfinder_review_policy(
            index_path,
            records,
            high_confidence=args.keyfinder_review_threshold,
            dry_run=args.dry_run,
            write_every=args.write_every,
            export_json=not args.no_json_export,
            max_examples=max(0, args.examples),
        )
        print(format_keyfinder_review_policy_report(report))
        if args.keyfinder_json:
            report_path = args.keyfinder_json.expanduser().resolve()
            write_keyfinder_report(report, report_path)
            print(f"KeyFinder review policy JSON: {report_path}")
        return 0
    if args.classification_audit:
        report = build_classification_audit_report(records, max_examples=max(0, args.examples))
        print(format_classification_audit_report(report))
        if args.classification_json:
            report_path = args.classification_json.expanduser().resolve()
            write_classification_audit_json(report, report_path)
            print(f"Classification audit JSON: {report_path}")
        if args.classification_csv:
            report_path = args.classification_csv.expanduser().resolve()
            write_classification_audit_csv(report, report_path)
            print(f"Classification audit CSV: {report_path}")
        return 0
    if args.keyfinder_experiment or args.keyfinder_enrich:
        try:
            library_roots = parse_library_roots(args.library_root)
            destination_roots = parse_library_roots(args.destination_root, option_name="--destination-root")
        except ValueError as exc:
            print(str(exc))
            return 2
        if args.keyfinder_enrich:
            report = enrich_keyfinder_metadata(
                index_path,
                records,
                library_roots=library_roots,
                destination_roots=destination_roots,
                limit=args.limit,
                scope=args.keyfinder_scope,
                low_confidence=args.low_confidence,
                convert_retry=args.keyfinder_convert_retry,
                keyfinder_workers=args.keyfinder_workers,
                dry_run=args.dry_run,
                write_every=args.write_every,
                export_json=not args.no_json_export,
            )
        else:
            report = build_keyfinder_experiment_report(
                records,
                library_roots=library_roots,
                destination_roots=destination_roots,
                limit=args.limit,
                scope=args.keyfinder_scope,
                low_confidence=args.low_confidence,
                convert_retry=args.keyfinder_convert_retry,
            )
        print(format_keyfinder_experiment_report(report))
        if args.keyfinder_json:
            report_path = args.keyfinder_json.expanduser().resolve()
            write_keyfinder_report(report, report_path)
            print(f"KeyFinder report JSON: {report_path}")
        return 2 if report.get("backend_error") == "keyfinder_not_found" else 0
    if args.deep_failures:
        report = build_deep_failure_report(records, max_examples=max(0, args.examples))
        print(format_deep_failure_report(report))
        if args.failures_json:
            json_path = args.failures_json.expanduser().resolve()
            write_deep_failure_json(report, json_path)
            print(f"Deep failure report JSON: {json_path}")
        if args.failures_csv:
            csv_path = args.failures_csv.expanduser().resolve()
            write_deep_failure_csv(report, csv_path)
            print(f"Deep failure report CSV: {csv_path}")
        return 0
    if args.deep_plan or args.deep_rerun:
        try:
            library_roots = parse_library_roots(args.library_root)
            destination_roots = parse_library_roots(args.destination_root, option_name="--destination-root")
        except ValueError as exc:
            print(str(exc))
            return 2
        plan = build_deep_review_plan(records, low_confidence=args.low_confidence, limit=args.limit, retry_deep_failed=args.retry_deep_failed)
        print(format_deep_review_plan(plan))
        if args.deep_rerun:
            rerun_summary = rerun_deep_review(
                index_path,
                plan["candidates"],
                library_roots=library_roots,
                destination_roots=destination_roots,
                analysis_duration=args.analysis_duration,
                sample_rate=args.sample_rate,
                analysis_profile=args.analysis_profile,
                engines=_parse_engines(args.engines),
                dry_run=args.dry_run,
                write_every=args.write_every,
                export_json=not args.no_json_export,
            )
            print("")
            print(format_deep_review_result(rerun_summary))
            if args.report_json:
                report_path = args.report_json.expanduser().resolve()
                write_deep_review_report(rerun_summary, report_path)
                print(f"Deep review report JSON: {report_path}")
        return 0

    summary = build_review_summary(records, max_examples=max(0, args.examples))
    print(format_review_summary(summary))
    return 0


def _percentage(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 2)


def _parse_engines(value: str | None) -> tuple[str, ...] | None:
    if not value:
        return None
    return tuple(engine.strip() for engine in value.split(",") if engine.strip())


if __name__ == "__main__":
    raise SystemExit(main())
