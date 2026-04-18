from __future__ import annotations

import argparse
from datetime import datetime, timezone
from collections import Counter
from dataclasses import dataclass, field, replace
import json
import os
import re
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

from sample_key_indexer.classify import classify_sample
from sample_key_indexer.discovery import SUPPORTED_EXTENSIONS
from sample_key_indexer.index_store import MetadataIndex, SQLiteMetadataIndex
from sample_key_indexer.models import AnalysisResult, file_signature
from sample_key_indexer.routing import route_file

DEFAULT_IGNORED_NAME_PATTERNS: tuple[str, ...] = (
    "fullmix",
    "full mix",
    "musicloop",
    "music loop",
)
REQUIRED_EXTERNAL_TOOLS: tuple[tuple[str, ...], ...] = (("keyfinder-cli", "keyfinder"),)
INFORMATIONAL_WARNING_CODES: tuple[str, ...] = ("short_signal_fft_adjusted",)


@dataclass
class FileTypeSummary:
    count: int = 0
    bytes: int = 0


@dataclass
class AnalysisRunSummary:
    errors: int = 0
    needs_review: int = 0
    low_confidence: int = 0
    key_disagreements: int = 0
    decoder_fallbacks: int = 0
    tiny_audio: int = 0
    warning_records: int = 0
    worker_crashes: int = 0
    isolated_retry_triggered: bool = False
    isolated_retry_files: int = 0
    error_examples: list[dict[str, object]] | None = None
    warning_examples: list[dict[str, object]] | None = None
    review_examples: list[dict[str, object]] | None = None
    crash_signature_counts: dict[str, int] | None = None
    crash_signature_examples: dict[str, dict[str, object]] | None = None
    warning_code_counts: dict[str, int] | None = None
    review_reason_counts: dict[str, int] | None = None

    def __post_init__(self) -> None:
        self.error_examples = list(self.error_examples or [])
        self.warning_examples = list(self.warning_examples or [])
        self.review_examples = list(self.review_examples or [])
        self.crash_signature_counts = dict(self.crash_signature_counts or {})
        self.crash_signature_examples = dict(self.crash_signature_examples or {})
        self.warning_code_counts = dict(self.warning_code_counts or {})
        self.review_reason_counts = dict(self.review_reason_counts or {})


@dataclass
class ProbeRunSummary:
    ffprobe: int = 0
    soundfile: int = 0
    librosa: int = 0
    unknown: int = 0
    failed: int = 0
    failed_reason_counts: dict[str, int] = field(default_factory=dict)
    failed_examples: list[dict[str, str]] = field(default_factory=list)


def _progress_bar():
    if not sys.stderr.isatty():
        return None
    try:
        from tqdm import tqdm  # type: ignore
    except Exception:
        return None
    return tqdm


def scan_library_files(root: Path) -> tuple[list[Path], dict[str, FileTypeSummary]]:
    """Single-pass filesystem scan that returns supported audio files + unsupported summary (with progress)."""
    supported: list[Path] = []
    unsupported: dict[str, FileTypeSummary] = {}
    progress = _progress_bar()
    iterator = (path for path in root.rglob("*") if path.is_file())
    if progress is not None:
        iterator = progress(iterator, desc="Scanning library", unit="file", mininterval=0.5)
    for path in iterator:
        extension = normalized_extension(path)
        if extension in SUPPORTED_EXTENSIONS:
            supported.append(path)
            continue
        summary = unsupported.setdefault(extension, FileTypeSummary())
        summary.count += 1
        summary.bytes += file_size(path)
    return supported, unsupported


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index and organise audio samples by detected key/root note.")
    parser.add_argument("input_root", type=Path, help="Root directory containing .wav, .mp3, .aiff, or .aif files.")
    parser.add_argument("output_root", type=Path, help="Directory where the organised library and metadata will be written.")
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)), help="Parallel analysis workers.")
    parser.add_argument("--analysis-duration", type=float, default=30.0, help="Max seconds loaded per file.")
    parser.add_argument("--sample-rate", type=int, default=22050, help="Analysis sample rate.")
    parser.add_argument("--index-file", type=Path, default=None, help="Metadata JSON path. Defaults to output_root/metadata_index.json.")
    parser.add_argument("--index-db", type=Path, default=None, help="SQLite index path. Defaults to output_root/metadata_index.sqlite.")
    parser.add_argument("--no-sqlite", action="store_true", help="Use the legacy JSON-only index instead of the V2 SQLite index.")
    parser.add_argument("--no-json-export", action="store_true", help="Do not export/update metadata_index.json when using SQLite.")
    parser.add_argument("--analysis-profile", choices=("fast", "balanced", "deep"), default="balanced", help="Analysis depth preset. balanced uses the normal librosa+essentia engine set.")
    parser.add_argument("--engines", default=None, help="Comma-separated analysis engines. Currently supports librosa and essentia.")
    parser.add_argument("--force", action="store_true", help="Reprocess files already present in the metadata index.")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying them.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and update destinations in metadata without copying/moving files.")
    parser.add_argument("--catalog-only", action="store_true", help="Analyze and write metadata without copying files into Key/ or Unsorted/.")
    parser.add_argument("--library-id", default=None, help="Stable ID for this source library or USB stick. Defaults to the input folder name.")
    parser.add_argument("--library-name", default=None, help="Display name for this source library or USB stick. Defaults to the library ID.")
    parser.add_argument("--write-every", type=int, default=100, help="Write metadata after this many processed files.")
    parser.add_argument("--max-duration", type=float, default=60.0, help="Skip files longer than this many seconds. Use 0 with --include-long-files to disable.")
    parser.add_argument("--include-long-files", action="store_true", help="Do not skip long files by duration.")
    parser.add_argument("--include-ignored-files", action="store_true", help="Analyze files that normally match ignored-name patterns such as fullmix/full mix.")
    parser.add_argument("--probe-backend", choices=("auto", "ffprobe", "python"), default="auto", help="Duration probe backend for skip decisions. auto uses ffprobe when available, then Python fallbacks.")
    parser.add_argument("--report-json", type=Path, default=None, help="Write a JSON run report. Defaults to output_root/analysis_run_report.json.")
    parser.add_argument("--doctor", action="store_true", help="Check the local audio-analysis environment and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from tqdm import tqdm
    except ModuleNotFoundError:
        tqdm = lambda iterable, **_: iterable

    from sample_key_indexer.audio_analysis import analyze_file, normalize_engines, validate_audio_backend

    selected_engines = normalize_engines(args.analysis_profile, _parse_engines(args.engines))

    try:
        backend_warnings = validate_audio_backend(selected_engines)
    except ModuleNotFoundError as exc:
        print(f"Audio backend check failed: missing module {exc.name!r}.")
        if exc.name == "_lzma":
            print("Your Python was built without LZMA/XZ support. Install xz and recreate the virtualenv with a Python that includes lzma.")
        return 2
    except Exception as exc:
        print(f"Audio backend check failed: {exc}")
        return 2

    if args.doctor:
        missing_tools = missing_required_external_tools()
        if missing_tools:
            print("Required external tool check failed.")
            for commands in missing_tools:
                print(f"Missing: {' or '.join(commands)}")
            return 2
        print("Audio backend check passed.")
        print("Required external tool check passed.")
        for warning in backend_warnings:
            print(f"Warning: {warning}")
        print(f"Analysis profile: {args.analysis_profile}; engines: {', '.join(selected_engines)}")
        return 0

    input_root = args.input_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    report_json_path = (args.report_json or output_root / "analysis_run_report.json").expanduser().resolve()
    library_id = args.library_id or slugify(input_root.name)
    library_name = args.library_name or library_id
    index_path = (args.index_file or output_root / "metadata_index.json").expanduser().resolve()
    index_db_path = (args.index_db or output_root / "metadata_index.sqlite").expanduser().resolve()
    if args.no_sqlite:
        index = MetadataIndex(index_path)
    else:
        index = SQLiteMetadataIndex(index_db_path, json_seed_path=index_path)

    unsupported_by_type = summarize_unsupported_files(input_root)
    files, unsupported_by_type = scan_library_files(input_root)
    if args.include_ignored_files:
        discovered_processable = files
        skipped_ignored: list[Path] = []
    else:
        discovered_processable, skipped_ignored = split_ignored_files(files)
    pending: list[Path] = []
    already_indexed: list[Path] = []
    for path in discovered_processable:
        if index.should_skip(path, force=args.force):
            already_indexed.append(path)
        else:
            pending.append(path)
    if args.include_long_files:
        processable = pending
        skipped_long = []
        probe_summary = ProbeRunSummary()
    else:
        processable, skipped_long, probe_summary = split_long_files(pending, args.max_duration, args.probe_backend)
    unsupported_count = sum(summary.count for summary in unsupported_by_type.values())
    print(f"Discovered {len(files)} supported audio files; {unsupported_count} unsupported files; {len(pending)} pending; {len(skipped_ignored)} ignored by filename; {len(skipped_long)} skipped as long files.")
    print(f"Analysis profile: {args.analysis_profile}; engines: {', '.join(selected_engines)}")
    for warning in backend_warnings:
        print(f"Warning: {warning}")

    processed = 0
    analysis_summary = AnalysisRunSummary()
    if processable:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(analyze_file, path, args.analysis_duration, args.sample_rate, args.analysis_profile, selected_engines): path
                for path in processable
            }
            for future in tqdm(as_completed(futures), total=len(futures), unit="file"):
                path = futures[future]
                try:
                    result = future.result()
                except BrokenProcessPool:
                    remaining = [pending_path for pending_future, pending_path in futures.items() if pending_future is future or not pending_future.done()]
                    print(f"Warning: worker process crashed while analyzing {path.name}. Retrying {len(remaining)} remaining files in isolated mode.")
                    analysis_summary.isolated_retry_triggered = True
                    analysis_summary.isolated_retry_files += len(remaining)
                    for isolated_path in tqdm(remaining, total=len(remaining), unit="file"):
                        isolated_result = analyze_file_isolated(isolated_path, args.analysis_duration, args.sample_rate, args.analysis_profile, selected_engines)
                        processed = store_indexed_result(
                            isolated_result,
                            output_root,
                            input_root,
                            library_id,
                            library_name,
                            index,
                            analysis_summary,
                            processed,
                            args.write_every,
                            move=args.move,
                            dry_run=args.dry_run or args.catalog_only,
                        )
                    break
                except Exception as exc:
                    result = worker_crash_result(path, args.analysis_profile, selected_engines, f"{type(exc).__name__}: {exc}")
                processed = store_indexed_result(
                    result,
                    output_root,
                    input_root,
                    library_id,
                    library_name,
                    index,
                    analysis_summary,
                    processed,
                    args.write_every,
                    move=args.move,
                    dry_run=args.dry_run or args.catalog_only,
                )

    index.write()
    if isinstance(index, SQLiteMetadataIndex):
        if not args.no_json_export:
            index.export_json(index_path)
        index.close()
        print(f"Indexed {processed} files. SQLite: {index_db_path}")
        if not args.no_json_export:
            print(f"Metadata JSON export: {index_path}")
    else:
        print(f"Indexed {processed} files. Metadata: {index_path}")
    print_copy_report(processed, already_indexed, skipped_ignored, skipped_long, unsupported_by_type, analysis_summary, probe_summary)
    write_run_report(
        report_json_path,
        processed=processed,
        input_root=input_root,
        output_root=output_root,
        library_id=library_id,
        library_name=library_name,
        selected_engines=selected_engines,
        analysis_profile=args.analysis_profile,
        skipped_ignored=skipped_ignored,
        skipped_long=skipped_long,
        already_indexed=already_indexed,
        unsupported_by_type=unsupported_by_type,
        analysis_summary=analysis_summary,
        probe_summary=probe_summary,
    )
    print(f"Run report JSON: {report_json_path}")
    return 0


def split_ignored_files(files: list[Path], patterns: tuple[str, ...] = DEFAULT_IGNORED_NAME_PATTERNS) -> tuple[list[Path], list[Path]]:
    processable: list[Path] = []
    skipped: list[Path] = []
    normalized_patterns = tuple(normalized_name_text(Path(pattern)) for pattern in patterns)
    for path in files:
        name = normalized_name_text(path)
        if any(pattern and pattern in name for pattern in normalized_patterns):
            skipped.append(path)
        else:
            processable.append(path)
    return processable, skipped


def split_long_files(files: list[Path], max_duration: float, probe_backend: str = "auto") -> tuple[list[Path], list[Path], ProbeRunSummary]:
    probe_summary = ProbeRunSummary()
    if max_duration <= 0:
        return files, [], probe_summary

    from sample_key_indexer.audio_analysis import probe_audio_file

    processable: list[Path] = []
    skipped: list[Path] = []
    progress = _progress_bar()
    iterator: object = files
    if progress is not None and files:
        iterator = progress(files, total=len(files), desc="Probing durations", unit="file", mininterval=0.5)
    for path in iterator:  # type: ignore[assignment]
        probe = probe_audio_file(path, probe_backend)
        record_probe_summary(probe_summary, probe)
        append_probe_failure_example(probe_summary, path, probe)
        duration = probe.duration
        if duration is not None and duration > max_duration:
            skipped.append(path)
        else:
            processable.append(path)
    return processable, skipped, probe_summary


def record_probe_summary(summary: ProbeRunSummary, probe) -> None:
    if probe.backend == "ffprobe":
        summary.ffprobe += 1
    elif probe.backend == "soundfile":
        summary.soundfile += 1
    elif probe.backend == "librosa":
        summary.librosa += 1
    else:
        summary.unknown += 1
    if probe.duration is None:
        summary.failed += 1
        reason = normalize_probe_error_reason(str(getattr(probe, "error", None) or "unknown_probe_error"))
        summary.failed_reason_counts[reason] = summary.failed_reason_counts.get(reason, 0) + 1


def append_probe_failure_example(summary: ProbeRunSummary, path: Path, probe) -> None:
    if probe.duration is not None or len(summary.failed_examples) >= 10:
        return
    summary.failed_examples.append(
        {
            "path": str(path),
            "backend": str(getattr(probe, "backend", "unknown")),
            "reason": normalize_probe_error_reason(str(getattr(probe, "error", None) or "unknown_probe_error")),
            "raw_error": str(getattr(probe, "error", None) or "unknown_probe_error"),
        }
    )


def normalize_probe_error_reason(reason: str) -> str:
    lowered = (reason or "").strip().lower()
    if not lowered:
        return "unknown_probe_error"
    if lowered.startswith("ffprobe_error:"):
        return "ffprobe_runtime_error"
    if lowered == "ffprobe_missing_duration":
        return "ffprobe_missing_duration"
    if lowered == "ffprobe_timeout":
        return "ffprobe_timeout"
    if lowered == "ffprobe_invalid_json":
        return "ffprobe_invalid_json"
    if lowered == "ffprobe_not_found":
        return "ffprobe_not_found"
    if "no audio streams" in lowered:
        return "no_audio_streams"
    if "pysoundfile failed" in lowered or "audioread" in lowered:
        return "python_decoder_fallback"
    if "illegal bit allocation value" in lowered or "layer i decoding" in lowered:
        return "mpeg_decoder_malformed_audio"
    if "unsupported" in lowered and "format" in lowered:
        return "unsupported_audio_format"
    return lowered[:120]


def attach_library_metadata(result, input_root: Path, library_id: str, library_name: str):
    source = Path(result.file_path)
    try:
        relative_path = str(source.relative_to(input_root))
    except ValueError:
        relative_path = source.name
    return replace(
        result,
        relative_path=relative_path,
        library_id=library_id,
        library_name=library_name,
        library_root=str(input_root),
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "sample_library"


def summarize_unsupported_files(root: Path, supported_extensions: set[str] = SUPPORTED_EXTENSIONS) -> dict[str, FileTypeSummary]:
    by_type: dict[str, FileTypeSummary] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        extension = normalized_extension(path)
        if extension in supported_extensions:
            continue
        summary = by_type.setdefault(extension, FileTypeSummary())
        summary.count += 1
        summary.bytes += file_size(path)
    return by_type


def summarize_paths_by_extension(paths: list[Path]) -> dict[str, FileTypeSummary]:
    by_type: dict[str, FileTypeSummary] = {}
    for path in paths:
        extension = normalized_extension(path)
        summary = by_type.setdefault(extension, FileTypeSummary())
        summary.count += 1
        summary.bytes += file_size(path)
    return by_type


def normalized_extension(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if suffix else "[no extension]"


def normalized_name_text(path: Path) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-./()]+", " ", path.stem.lower())).strip()


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def print_copy_report(
    processed: int,
    already_indexed: list[Path],
    skipped_ignored: list[Path],
    skipped_long: list[Path],
    unsupported_by_type: dict[str, FileTypeSummary],
    analysis_summary: AnalysisRunSummary | None = None,
    probe_summary: ProbeRunSummary | None = None,
) -> None:
    ignored_bytes = sum(file_size(path) for path in skipped_ignored)
    long_bytes = sum(file_size(path) for path in skipped_long)
    unsupported_bytes = sum(summary.bytes for summary in unsupported_by_type.values())
    explained_delta_bytes = ignored_bytes + long_bytes + unsupported_bytes

    print("")
    print("Copy report:")
    print(f"  Processed this run: {processed} files")
    print(f"  Already indexed/resumed: {len(already_indexed)} files ({format_gb(sum(file_size(path) for path in already_indexed))})")
    print(f"  Not copied - ignored filename patterns: {len(skipped_ignored)} files ({format_gb(ignored_bytes)})")
    for extension, summary in sorted(summarize_paths_by_extension(skipped_ignored).items(), key=lambda item: item[1].bytes, reverse=True):
        print(f"    {extension}: {summary.count} files ({format_gb(summary.bytes)})")
    print(f"  Not copied - long files: {len(skipped_long)} files ({format_gb(long_bytes)})")
    for extension, summary in sorted(summarize_paths_by_extension(skipped_long).items(), key=lambda item: item[1].bytes, reverse=True):
        print(f"    {extension}: {summary.count} files ({format_gb(summary.bytes)})")
    print(f"  Not copied - unsupported file types: {sum(summary.count for summary in unsupported_by_type.values())} files ({format_gb(unsupported_bytes)})")
    for extension, summary in sorted(unsupported_by_type.items(), key=lambda item: item[1].bytes, reverse=True):
        print(f"    {extension}: {summary.count} files ({format_gb(summary.bytes)})")
    if probe_summary:
        print("Duration probe report:")
        print(f"  ffprobe: {probe_summary.ffprobe} files")
        print(f"  soundfile fallback: {probe_summary.soundfile} files")
        print(f"  librosa fallback: {probe_summary.librosa} files")
        print(f"  Unknown backend: {probe_summary.unknown} files")
        print(f"  Failed duration probes: {probe_summary.failed} files")
        if probe_summary.failed_reason_counts:
            print("  Failed probe reasons:")
            for reason, count in sorted(probe_summary.failed_reason_counts.items(), key=lambda item: (-item[1], item[0]))[:8]:
                print(f"    - {reason}: {count}")
        if probe_summary.failed_examples:
            print("  Failed probe examples:")
            for item in probe_summary.failed_examples[:5]:
                print(f"    - {item['backend']} | {item['reason']} | {item['path']}")
    if analysis_summary:
        print("Analysis report:")
        print(f"  Errors: {analysis_summary.errors} files")
        print(f"  Needs review: {analysis_summary.needs_review} files")
        print(f"  Low confidence: {analysis_summary.low_confidence} files")
        print(f"  Key disagreements: {analysis_summary.key_disagreements} files")
        print(f"  Decoder fallbacks: {analysis_summary.decoder_fallbacks} files")
        print(f"  Tiny/near-silent audio: {analysis_summary.tiny_audio} files")
        print(f"  Files with warnings: {analysis_summary.warning_records} files")
        print(f"  Worker crashes: {analysis_summary.worker_crashes} files")
        if analysis_summary.isolated_retry_triggered:
            print(f"  Isolated retry mode: triggered for {analysis_summary.isolated_retry_files} files")
    print(f"  Explained source/output delta from skipped files: {format_gb(explained_delta_bytes)}")


def update_analysis_summary(summary: AnalysisRunSummary, result) -> None:
    warnings = result.analysis_warnings or []
    review_reasons = result.review_reasons or []
    actionable_warnings = [warning for warning in warnings if not is_informational_warning(warning)]
    if result.error:
        summary.errors += 1
        if "worker_crash" in str(result.error) or "worker_crash" in warnings or "worker_crash" in review_reasons:
            summary.worker_crashes += 1
        record_crash_signature(summary, result)
        append_example(
            summary.error_examples,
            build_result_example(result),
        )
    if result.needs_review:
        summary.needs_review += 1
        for reason in review_reasons:
            if summary.review_reason_counts is not None:
                summary.review_reason_counts[reason] = summary.review_reason_counts.get(reason, 0) + 1
        append_example(
            summary.review_examples,
            build_result_example(result),
        )
    if result.confidence < 0.35:
        summary.low_confidence += 1
    if any("key_disagreement" in reason or "root_disagreement" in reason for reason in review_reasons):
        summary.key_disagreements += 1
    if "decoder_fallback_audioread" in actionable_warnings:
        summary.decoder_fallbacks += 1
    if any(reason in {"tiny_audio", "near_silence"} for reason in [*warnings, *review_reasons]):
        summary.tiny_audio += 1
    if actionable_warnings:
        for warning in actionable_warnings:
            if summary.warning_code_counts is not None:
                summary.warning_code_counts[warning] = summary.warning_code_counts.get(warning, 0) + 1
        summary.warning_records += 1
        append_example(
            summary.warning_examples,
            build_result_example(result),
        )


def format_gb(bytes_count: int) -> str:
    return f"{bytes_count / 1_000_000_000:.2f} GB"


def is_informational_warning(value: str) -> bool:
    return value in INFORMATIONAL_WARNING_CODES or value.startswith("DeprecationWarning:")


def normalize_crash_signature(result: AnalysisResult) -> str:
    error = (result.error or "unknown_error").strip()
    error_head = error.split(":", 1)[0].strip() or "unknown_error"
    warnings = sorted(set(result.analysis_warnings or []))
    review_reasons = sorted(reason for reason in set(result.review_reasons or []) if reason == "worker_crash")
    engines = ",".join(result.analysis_engines or [])
    parts = [error_head]
    if warnings:
        parts.append(f"warnings={','.join(warnings)}")
    if review_reasons:
        parts.append(f"review={','.join(review_reasons)}")
    if result.analysis_profile:
        parts.append(f"profile={result.analysis_profile}")
    if engines:
        parts.append(f"engines={engines}")
    return " | ".join(parts)


def record_crash_signature(summary: AnalysisRunSummary, result: AnalysisResult) -> None:
    if not result.error:
        return
    signature = normalize_crash_signature(result)
    counts = summary.crash_signature_counts
    examples = summary.crash_signature_examples
    if counts is None or examples is None:
        return
    counts[signature] = counts.get(signature, 0) + 1
    examples.setdefault(signature, build_result_example(result))


def append_example(bucket: list[dict[str, object]] | None, example: dict[str, object], *, limit: int = 20) -> None:
    if bucket is None or len(bucket) >= limit:
        return
    bucket.append(example)


def build_result_example(result: AnalysisResult) -> dict[str, object]:
    return {
        "name": Path(result.file_path).name,
        "file_path": result.file_path,
        "relative_path": result.relative_path,
        "category": result.category,
        "type": result.type,
        "confidence": result.confidence,
        "warnings": list(result.analysis_warnings or []),
        "review_reasons": list(result.review_reasons or []),
        "error": result.error,
        "library_id": result.library_id,
        "library_name": result.library_name,
        "key": result.key,
        "root_note": result.root_note,
    }


def write_run_report(
    path: Path,
    *,
    processed: int,
    input_root: Path,
    output_root: Path,
    library_id: str,
    library_name: str,
    selected_engines: tuple[str, ...],
    analysis_profile: str,
    skipped_ignored: list[Path],
    skipped_long: list[Path],
    already_indexed: list[Path],
    unsupported_by_type: dict[str, FileTypeSummary],
    analysis_summary: AnalysisRunSummary,
    probe_summary: ProbeRunSummary,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "library": {
            "id": library_id,
            "name": library_name,
            "input_root": str(input_root),
            "output_root": str(output_root),
        },
        "analysis": {
            "profile": analysis_profile,
            "engines": list(selected_engines),
        },
        "summary": {
            "processed": processed,
            "already_indexed": len(already_indexed),
            "ignored_by_filename": len(skipped_ignored),
            "skipped_long": len(skipped_long),
            "unsupported_files": sum(summary.count for summary in unsupported_by_type.values()),
            "errors": analysis_summary.errors,
            "needs_review": analysis_summary.needs_review,
            "low_confidence": analysis_summary.low_confidence,
            "key_disagreements": analysis_summary.key_disagreements,
            "decoder_fallbacks": analysis_summary.decoder_fallbacks,
            "tiny_audio": analysis_summary.tiny_audio,
            "warning_records": analysis_summary.warning_records,
            "worker_crashes": analysis_summary.worker_crashes,
            "isolated_retry_triggered": analysis_summary.isolated_retry_triggered,
            "isolated_retry_files": analysis_summary.isolated_retry_files,
        },
        "probe_summary": {
            "ffprobe": probe_summary.ffprobe,
            "soundfile": probe_summary.soundfile,
            "librosa": probe_summary.librosa,
            "unknown": probe_summary.unknown,
            "failed": probe_summary.failed,
            "failed_reason_counts": serialize_counter(probe_summary.failed_reason_counts),
            "failed_examples": probe_summary.failed_examples,
        },
        "skips": {
            "already_indexed_bytes": sum(file_size(path) for path in already_indexed),
            "ignored_by_filename_bytes": sum(file_size(path) for path in skipped_ignored),
            "skipped_long_bytes": sum(file_size(path) for path in skipped_long),
            "explained_source_output_delta_bytes": sum(file_size(path) for path in skipped_ignored)
            + sum(file_size(path) for path in skipped_long)
            + sum(summary.bytes for summary in unsupported_by_type.values()),
            "ignored_by_filename_by_extension": serialize_filetype_summary(summarize_paths_by_extension(skipped_ignored)),
            "skipped_long_by_extension": serialize_filetype_summary(summarize_paths_by_extension(skipped_long)),
            "unsupported_by_extension": serialize_filetype_summary(unsupported_by_type),
        },
        "reason_counts": {
            "warnings": serialize_counter(analysis_summary.warning_code_counts),
            "review": serialize_counter(analysis_summary.review_reason_counts),
        },
        "examples": {
            "errors": analysis_summary.error_examples,
            "warnings": analysis_summary.warning_examples,
            "needs_review": analysis_summary.review_examples,
        },
        "crash_signatures": serialize_crash_signatures(analysis_summary),
        "suspicious_files": build_suspicious_file_report(analysis_summary, probe_summary),
    }
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def serialize_filetype_summary(by_type: dict[str, FileTypeSummary]) -> list[dict[str, object]]:
    return [
        {"extension": extension, "count": summary.count, "bytes": summary.bytes}
        for extension, summary in sorted(by_type.items(), key=lambda item: item[1].bytes, reverse=True)
    ]


def serialize_crash_signatures(summary: AnalysisRunSummary) -> list[dict[str, object]]:
    counts = summary.crash_signature_counts or {}
    examples = summary.crash_signature_examples or {}
    return [
        {
            "signature": signature,
            "count": count,
            "example": examples.get(signature),
        }
        for signature, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def serialize_counter(counter: dict[str, int] | None) -> list[dict[str, object]]:
    counts = counter or {}
    return [{"value": value, "count": count} for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def build_suspicious_file_report(analysis_summary: AnalysisRunSummary, probe_summary: ProbeRunSummary) -> dict[str, object]:
    counts = Counter()
    counts.update(probe_summary.failed_reason_counts or {})
    counts.update(analysis_summary.warning_code_counts or {})
    if analysis_summary.tiny_audio:
        counts["tiny_or_near_silent_audio"] += analysis_summary.tiny_audio
    if analysis_summary.worker_crashes:
        counts["worker_crash"] += analysis_summary.worker_crashes
    examples: list[dict[str, object]] = []
    for item in probe_summary.failed_examples:
        if len(examples) >= 20:
            break
        examples.append(
            {
                "source": "probe",
                "path": item.get("path"),
                "reason": item.get("reason"),
                "raw_error": item.get("raw_error"),
            }
        )
    for bucket_name, bucket in (("warning", analysis_summary.warning_examples), ("error", analysis_summary.error_examples)):
        for item in bucket or []:
            if len(examples) >= 20:
                break
            examples.append(
                {
                    "source": bucket_name,
                    "name": item.get("name"),
                    "relative_path": item.get("relative_path"),
                    "warnings": item.get("warnings"),
                    "review_reasons": item.get("review_reasons"),
                    "error": item.get("error"),
                }
            )
    return {
        "counts": serialize_counter(dict(counts)),
        "examples": examples,
    }


def _parse_engines(value: str | None) -> tuple[str, ...] | None:
    if not value:
        return None
    return tuple(engine.strip() for engine in value.split(",") if engine.strip())


def analyze_file_isolated(
    path: Path,
    analysis_duration: float,
    sample_rate: int,
    analysis_profile: str,
    selected_engines: tuple[str, ...],
) -> AnalysisResult:
    from sample_key_indexer.audio_analysis import analyze_file

    try:
        with ProcessPoolExecutor(max_workers=1) as pool:
            future = pool.submit(analyze_file, path, analysis_duration, sample_rate, analysis_profile, selected_engines)
            return future.result()
    except BrokenProcessPool:
        return worker_crash_result(path, analysis_profile, selected_engines, "worker_crash")
    except Exception as exc:
        return worker_crash_result(path, analysis_profile, selected_engines, f"{type(exc).__name__}: {exc}")


def worker_crash_result(
    path: Path,
    analysis_profile: str,
    selected_engines: tuple[str, ...],
    reason: str,
) -> AnalysisResult:
    category, sample_type = classify_sample(path, 0.0, None, None)
    signature = file_signature(path)
    return AnalysisResult(
        file_path=str(path),
        root_note=None,
        key=None,
        confidence=0.0,
        category=category,
        type=sample_type,
        duration=0.0,
        sample_rate=None,
        format=path.suffix.lower().lstrip("."),
        analysis_profile=analysis_profile,
        analysis_engines=list(selected_engines),
        analysis_warnings=["worker_crash"],
        needs_review=True,
        review_reasons=["worker_crash"],
        error=reason,
        size=int(signature["size"]),
        mtime=float(signature["mtime"]),
    )


def store_indexed_result(
    result: AnalysisResult,
    output_root: Path,
    input_root: Path,
    library_id: str,
    library_name: str,
    index,
    analysis_summary: AnalysisRunSummary,
    processed: int,
    write_every: int,
    *,
    move: bool,
    dry_run: bool,
) -> int:
    routed = route_file(result, output_root, move=move, dry_run=dry_run)
    routed = attach_library_metadata(routed, input_root, library_id, library_name)
    index.upsert(routed)
    update_analysis_summary(analysis_summary, routed)
    processed += 1
    if processed % max(1, write_every) == 0:
        index.write()
    return processed


def missing_required_external_tools() -> list[tuple[str, ...]]:
    return [commands for commands in REQUIRED_EXTERNAL_TOOLS if not any(shutil.which(command) for command in commands)]


if __name__ == "__main__":
    raise SystemExit(main())
