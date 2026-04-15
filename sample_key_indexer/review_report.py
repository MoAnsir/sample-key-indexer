from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sample_key_indexer.audio_analysis import analyze_file, normalize_engines
from sample_key_indexer.index_store import MetadataIndex, SQLiteMetadataIndex, load_records
from sample_key_indexer.web_app import _flatten_sample, _playable_path, parse_library_roots

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
    },
    {
        "id": "sonic_annotator",
        "label": "Sonic Annotator",
        "commands": ("sonic-annotator",),
        "version_args": ("--version",),
        "purpose": "Vamp plugin runner for QM key/chord plugins.",
    },
    {
        "id": "aubio",
        "label": "aubio",
        "commands": ("aubio",),
        "version_args": ("--version",),
        "purpose": "Small-footprint onset/tempo utility, not a primary key backend.",
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
    return {
        "deep_failure_targets": {
            "total": failure_report["total"],
            "by_reason": failure_report["by_reason"],
            "by_format": failure_report["by_format"],
            "by_duration": failure_report["by_duration"],
            "by_path_family": failure_report["by_path_family"],
            "triage_hints": failure_report["triage_hints"],
        },
        "backend_status": discover_deep_backends(),
    }


def build_keyfinder_experiment_report(
    records: list[dict[str, Any]],
    library_roots: dict[str, Path] | None = None,
    destination_roots: dict[str, Path] | None = None,
    limit: int = 0,
    timeout: float = 15.0,
    scope: str = "failures",
    low_confidence: float = 0.35,
) -> dict[str, Any]:
    command = shutil.which("keyfinder-cli") or shutil.which("keyfinder")
    targets = keyfinder_targets(records, scope=scope, low_confidence=low_confidence)
    if limit > 0:
        targets = targets[:limit]
    report: dict[str, Any] = {
        "backend": "keyfinder",
        "scope": scope,
        "command": command,
        "selected": len(targets),
        "processed": 0,
        "successes": 0,
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


def keyfinder_targets(records: list[dict[str, Any]], scope: str, low_confidence: float = 0.35) -> list[dict[str, Any]]:
    if scope == "failures":
        return build_deep_failure_report(records, max_examples=0)["failures"]
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
        return {"status": "error", "error": raw_output or f"exit_{completed.returncode}", "raw_output": raw_output}
    raw_key = raw_output.splitlines()[0].strip() if raw_output else ""
    normalized_key, root_note = normalize_keyfinder_key(raw_key)
    return {
        "status": "success" if raw_key else "error",
        "raw_key": raw_key or None,
        "normalized_key": normalized_key,
        "root_note": root_note,
        "raw_output": raw_output,
        "error": None if raw_key else "empty_output",
    }


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
            }
    return {
        "id": spec["id"],
        "label": spec["label"],
        "status": "missing",
        "command": None,
        "path": None,
        "version": None,
        "purpose": spec["purpose"],
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
        lines.append(f"- {backend['label']}: {backend['status']} ({detail})")
        if backend.get("version"):
            lines.append(f"  Version: {backend['version']}")
        lines.append(f"  Role: {backend['purpose']}")
    qm_plugins = status["qm_vamp_plugins"]
    lines.append(f"- QM Vamp Plugins: {qm_plugins['status']}")
    if qm_plugins["matches"]:
        for match in qm_plugins["matches"][:10]:
            lines.append(f"  - {match}")
    else:
        lines.append("  No qm-named Vamp plugin files found in the standard macOS/Homebrew Vamp paths.")
    lines.append("")
    lines.append("Next experiment:")
    lines.append("- If Sonic Annotator and QM Vamp Plugins are available, test them first against the recorded deep failures.")
    lines.append("- If KeyFinder CLI is available, compare its key output against the same failure set.")
    lines.append("- Keep aubio optional for tempo/onset checks rather than primary key detection.")
    return "\n".join(lines)


def format_keyfinder_experiment_report(report: dict[str, Any]) -> str:
    lines = [
        "KeyFinder experiment:",
        f"  Scope: {report.get('scope') or 'failures'}",
        f"  Command: {report.get('command') or 'not found'}",
        f"  Selected samples: {report['selected']} files",
        f"  Processed: {report['processed']} files",
        f"  Successes: {report['successes']} files",
        f"  Missing audio: {report['missing_audio']} files",
        f"  Errors: {report['errors']} files",
        f"  Matches stored key: {report['matches_stored_key']} files",
        f"  Matches stored root: {report['matches_stored_root']} files",
    ]
    if report.get("backend_error"):
        lines.append(f"  Backend error: {report['backend_error']}")
    if report.get("error_reasons"):
        lines.append("")
        lines.append("Error reasons:")
        for item in report["error_reasons"][:10]:
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
    return "\n".join(lines)


def write_deep_failure_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def write_keyfinder_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


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
    parser.add_argument("--deep-plan", action="store_true", help="Print the V3.3 deep-review candidate plan.")
    parser.add_argument("--deep-rerun", action="store_true", help="Rerun analysis only for deep-review candidates and update the index.")
    parser.add_argument("--deep-failures", action="store_true", help="Print the V3.5 deep-review failure report.")
    parser.add_argument("--backend-check", action="store_true", help="Print the V3.6 optional deep-backend availability report.")
    parser.add_argument("--keyfinder-experiment", action="store_true", help="Run KeyFinder CLI against recorded deep-review failures without updating metadata.")
    parser.add_argument("--keyfinder-scope", choices=("failures", "review", "all"), default="failures", help="Samples to send to KeyFinder: failed deep-review records, review candidates, or the full index.")
    parser.add_argument("--dry-run", action="store_true", help="Preview deep-review rerun counts without updating metadata.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum deep-review candidates to select. 0 means no limit.")
    parser.add_argument("--low-confidence", type=float, default=0.35, help="Select records below this confidence for deep review.")
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
    if args.backend_check:
        print(format_backend_check_report(build_backend_check_report(records)))
        return 0
    if args.keyfinder_experiment:
        try:
            library_roots = parse_library_roots(args.library_root)
            destination_roots = parse_library_roots(args.destination_root, option_name="--destination-root")
        except ValueError as exc:
            print(str(exc))
            return 2
        report = build_keyfinder_experiment_report(
            records,
            library_roots=library_roots,
            destination_roots=destination_roots,
            limit=args.limit,
            scope=args.keyfinder_scope,
            low_confidence=args.low_confidence,
        )
        print(format_keyfinder_experiment_report(report))
        if args.keyfinder_json:
            report_path = args.keyfinder_json.expanduser().resolve()
            write_keyfinder_report(report, report_path)
            print(f"KeyFinder report JSON: {report_path}")
        return 0
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
