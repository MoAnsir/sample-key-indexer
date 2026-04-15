from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from sample_key_indexer.discovery import SUPPORTED_EXTENSIONS, discover_audio_files
from sample_key_indexer.index_store import MetadataIndex, SQLiteMetadataIndex
from sample_key_indexer.routing import route_file


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


@dataclass
class ProbeRunSummary:
    ffprobe: int = 0
    soundfile: int = 0
    librosa: int = 0
    unknown: int = 0
    failed: int = 0


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
    parser.add_argument("--analysis-profile", choices=("fast", "balanced", "deep"), default="balanced", help="Analysis depth preset. balanced adds optional V2 engines when installed.")
    parser.add_argument("--engines", default=None, help="Comma-separated analysis engines. Currently supports librosa and optional essentia.")
    parser.add_argument("--force", action="store_true", help="Reprocess files already present in the metadata index.")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying them.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and update destinations in metadata without copying/moving files.")
    parser.add_argument("--catalog-only", action="store_true", help="Analyze and write metadata without copying files into Key/ or Unsorted/.")
    parser.add_argument("--library-id", default=None, help="Stable ID for this source library or USB stick. Defaults to the input folder name.")
    parser.add_argument("--library-name", default=None, help="Display name for this source library or USB stick. Defaults to the library ID.")
    parser.add_argument("--write-every", type=int, default=100, help="Write metadata after this many processed files.")
    parser.add_argument("--max-duration", type=float, default=60.0, help="Skip files longer than this many seconds. Use 0 with --include-long-files to disable.")
    parser.add_argument("--include-long-files", action="store_true", help="Do not skip long files by duration.")
    parser.add_argument("--probe-backend", choices=("auto", "ffprobe", "python"), default="auto", help="Duration probe backend for skip decisions. auto uses ffprobe when available, then Python fallbacks.")
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
        print("Audio backend check passed.")
        for warning in backend_warnings:
            print(f"Warning: {warning}")
        print(f"Analysis profile: {args.analysis_profile}; engines: {', '.join(selected_engines)}")
        return 0

    input_root = args.input_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    library_id = args.library_id or slugify(input_root.name)
    library_name = args.library_name or library_id
    index_path = (args.index_file or output_root / "metadata_index.json").expanduser().resolve()
    index_db_path = (args.index_db or output_root / "metadata_index.sqlite").expanduser().resolve()
    if args.no_sqlite:
        index = MetadataIndex(index_path)
    else:
        index = SQLiteMetadataIndex(index_db_path, json_seed_path=index_path)

    unsupported_by_type = summarize_unsupported_files(input_root)
    files = discover_audio_files(input_root)
    pending: list[Path] = []
    already_indexed: list[Path] = []
    for path in files:
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
    print(f"Discovered {len(files)} supported audio files; {unsupported_count} unsupported files; {len(pending)} pending; {len(skipped_long)} skipped as long files.")
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
                result = future.result()
                routed = route_file(result, output_root, move=args.move, dry_run=args.dry_run or args.catalog_only)
                routed = attach_library_metadata(routed, input_root, library_id, library_name)
                index.upsert(routed)
                update_analysis_summary(analysis_summary, routed)
                processed += 1
                if processed % max(1, args.write_every) == 0:
                    index.write()

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
    print_copy_report(processed, already_indexed, skipped_long, unsupported_by_type, analysis_summary, probe_summary)
    return 0


def split_long_files(files: list[Path], max_duration: float, probe_backend: str = "auto") -> tuple[list[Path], list[Path], ProbeRunSummary]:
    probe_summary = ProbeRunSummary()
    if max_duration <= 0:
        return files, [], probe_summary

    from sample_key_indexer.audio_analysis import probe_audio_file

    processable: list[Path] = []
    skipped: list[Path] = []
    for path in files:
        probe = probe_audio_file(path, probe_backend)
        record_probe_summary(probe_summary, probe)
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


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def print_copy_report(
    processed: int,
    already_indexed: list[Path],
    skipped_long: list[Path],
    unsupported_by_type: dict[str, FileTypeSummary],
    analysis_summary: AnalysisRunSummary | None = None,
    probe_summary: ProbeRunSummary | None = None,
) -> None:
    print("")
    print("Copy report:")
    print(f"  Processed this run: {processed} files")
    print(f"  Already indexed/resumed: {len(already_indexed)} files ({format_gb(sum(file_size(path) for path in already_indexed))})")
    print(f"  Not copied - long files: {len(skipped_long)} files ({format_gb(sum(file_size(path) for path in skipped_long))})")
    for extension, summary in sorted(summarize_paths_by_extension(skipped_long).items(), key=lambda item: item[1].bytes, reverse=True):
        print(f"    {extension}: {summary.count} files ({format_gb(summary.bytes)})")
    print(f"  Not copied - unsupported file types: {sum(summary.count for summary in unsupported_by_type.values())} files ({format_gb(sum(summary.bytes for summary in unsupported_by_type.values()))})")
    for extension, summary in sorted(unsupported_by_type.items(), key=lambda item: item[1].bytes, reverse=True):
        print(f"    {extension}: {summary.count} files ({format_gb(summary.bytes)})")
    if probe_summary:
        print("Duration probe report:")
        print(f"  ffprobe: {probe_summary.ffprobe} files")
        print(f"  soundfile fallback: {probe_summary.soundfile} files")
        print(f"  librosa fallback: {probe_summary.librosa} files")
        print(f"  Unknown backend: {probe_summary.unknown} files")
        print(f"  Failed duration probes: {probe_summary.failed} files")
    if analysis_summary:
        print("Analysis report:")
        print(f"  Errors: {analysis_summary.errors} files")
        print(f"  Needs review: {analysis_summary.needs_review} files")
        print(f"  Low confidence: {analysis_summary.low_confidence} files")
        print(f"  Key disagreements: {analysis_summary.key_disagreements} files")
        print(f"  Decoder fallbacks: {analysis_summary.decoder_fallbacks} files")
        print(f"  Tiny/near-silent audio: {analysis_summary.tiny_audio} files")
        print(f"  Files with warnings: {analysis_summary.warning_records} files")


def update_analysis_summary(summary: AnalysisRunSummary, result) -> None:
    warnings = result.analysis_warnings or []
    review_reasons = result.review_reasons or []
    if result.error:
        summary.errors += 1
    if result.needs_review:
        summary.needs_review += 1
    if result.confidence < 0.35:
        summary.low_confidence += 1
    if any("key_disagreement" in reason or "root_disagreement" in reason for reason in review_reasons):
        summary.key_disagreements += 1
    if "decoder_fallback_audioread" in warnings:
        summary.decoder_fallbacks += 1
    if any(reason in {"tiny_audio", "near_silence"} for reason in [*warnings, *review_reasons]):
        summary.tiny_audio += 1
    if warnings:
        summary.warning_records += 1


def format_gb(bytes_count: int) -> str:
    return f"{bytes_count / 1_000_000_000:.2f} GB"


def _parse_engines(value: str | None) -> tuple[str, ...] | None:
    if not value:
        return None
    return tuple(engine.strip() for engine in value.split(",") if engine.strip())


if __name__ == "__main__":
    raise SystemExit(main())
