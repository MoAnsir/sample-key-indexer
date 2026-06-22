from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sample_key_indexer.discovery import SUPPORTED_EXTENSIONS

IGNORED_NAME_PATTERNS: tuple[str, ...] = (
    "fullmix",
    "full mix",
    "mainmix",
    "main mix",
    "musicloop",
    "music loop",
    # Common "this is a full track" naming baggage in sample packs.
    # We treat these as "always removable" rather than duration-gated, because they are
    # almost never the reusable one-shot/loop content.
    "original mix",
    "extended mix",
    "radio edit",
    "instrumental",
    "a cappella",
    "acapella",
    "album version",
    "clean version",
    "dirty version",
    "stereo mix",
    "2 track",
    "2track",
    "mix master",
    "premaster",
    "pre master",
    "mastered",
)

DEMO_MIN_SECONDS_DEFAULT = 60.0
MIX_MIN_SECONDS_DEFAULT = 60.0
SONG_MIN_SECONDS_DEFAULT = 60.0

PACK_BAGGAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt",
        ".rtf",
        ".nfo",
        ".pdf",
        ".doc",
        ".docx",
        ".md",
        ".url",
        ".webloc",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".icns",
        ".plist",
    }
)


@dataclass(frozen=True)
class SanitizeItem:
    path: str
    relative_path: str
    extension: str
    bytes: int
    reason: str


SUSPICIOUS_EXAMPLE_LIMIT = 50


@dataclass(frozen=True)
class _ProbeRequest:
    path: Path
    relative_path: str
    extension: str
    bytes: int
    wants_demo_check: bool
    wants_mix_check: bool
    wants_song_check: bool
    wants_openable_check: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan a source sample library and quarantine or delete unsupported/full-arrangement files in place."
    )
    parser.add_argument("input_root", type=Path, help="Root sample folder to clean in place.")
    parser.add_argument("--report-json", type=Path, default=None, help="Write a JSON sanitize report. Defaults to input_root/sanitize_report.json.")
    parser.add_argument(
        "--quarantine-dir",
        type=Path,
        default=None,
        help="Where to move quarantined files. Defaults to a sibling folder named <input_root>__quarantine.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print the pre-action report and write JSON; do not prompt or change files.")
    parser.add_argument(
        "--action",
        choices=("prompt", "quarantine", "delete", "cancel"),
        default="prompt",
        help="Override the interactive choice. delete still requires confirmation unless --yes is set.",
    )
    parser.add_argument("--yes", action="store_true", help="Skip the final DELETE confirmation when used with --action delete.")
    parser.add_argument(
        "--demo-min-seconds",
        type=float,
        default=DEMO_MIN_SECONDS_DEFAULT,
        help="When a supported audio filename contains the word 'demo', remove it only if its duration exceeds this many seconds. Default: 60.",
    )
    parser.add_argument(
        "--mix-min-seconds",
        type=float,
        default=MIX_MIN_SECONDS_DEFAULT,
        help="When a supported audio filename contains the word 'mix', remove it only if its duration exceeds this many seconds. Default: 60.",
    )
    parser.add_argument(
        "--song-min-seconds",
        type=float,
        default=SONG_MIN_SECONDS_DEFAULT,
        help="When a supported audio filename contains the word 'song' or 'track', remove it only if its duration exceeds this many seconds. Default: 60.",
    )
    parser.add_argument(
        "--remove-unopenable-audio",
        action="store_true",
        help="Also remove/quarantine supported audio files that ffprobe cannot open (corrupt/unhandled). Default: off.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(8, os.cpu_count() or 1)),
        help="Parallelism for ffprobe-based checks (demo duration, unopenable audio). Default: 8 (capped).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_root = args.input_root.expanduser().resolve()
    report_path = (args.report_json or (input_root / "sanitize_report.json")).expanduser().resolve()
    quarantine_dir = default_quarantine_dir(input_root) if args.quarantine_dir is None else args.quarantine_dir.expanduser().resolve()

    validation_error = validate_input_root(input_root, quarantine_dir)
    if validation_error:
        print(validation_error)
        _ensure_cursor_visible()
        return 2

    started = time.time()
    try:
        scan = scan_sanitization_candidates(
            input_root,
            demo_min_seconds=float(args.demo_min_seconds),
            mix_min_seconds=float(args.mix_min_seconds),
            song_min_seconds=float(args.song_min_seconds),
            remove_unopenable_audio=bool(args.remove_unopenable_audio),
            workers=int(args.workers),
        )
        print_pre_action_report(input_root, scan)
    finally:
        # tqdm/input combos can sometimes leave the cursor hidden; be explicit.
        _ensure_cursor_visible()

    if int(scan["removable_count"]) == 0:
        report = build_report(
            input_root=input_root,
            quarantine_dir=quarantine_dir,
            scan=scan,
            action="noop",
            moved=[],
            deleted=[],
            cancelled=False,
            elapsed_seconds=time.time() - started,
        )
        write_report(report_path, report)
        print("")
        print("Nothing matched the sanitization rules. No files were changed.")
        print(f"Report JSON: {report_path}")
        return 0

    if args.dry_run:
        report = build_report(
            input_root=input_root,
            quarantine_dir=quarantine_dir,
            scan=scan,
            action="dry_run",
            moved=[],
            deleted=[],
            cancelled=False,
            elapsed_seconds=time.time() - started,
        )
        write_report(report_path, report)
        print("")
        print(f"Dry run only. Report JSON: {report_path}")
        return 0

    action = resolve_action(args.action)
    if action == "prompt":
        action = prompt_for_action()

    if action == "cancel":
        report = build_report(
            input_root=input_root,
            quarantine_dir=quarantine_dir,
            scan=scan,
            action="cancelled",
            moved=[],
            deleted=[],
            cancelled=True,
            elapsed_seconds=time.time() - started,
        )
        write_report(report_path, report)
        print("")
        print("Cancelled. No files were changed.")
        print(f"Report JSON: {report_path}")
        return 0

    if action == "delete" and not args.yes:
        if not confirm_delete(scan):
            report = build_report(
                input_root=input_root,
                quarantine_dir=quarantine_dir,
                scan=scan,
                action="cancelled",
                moved=[],
                deleted=[],
                cancelled=True,
                elapsed_seconds=time.time() - started,
            )
            write_report(report_path, report)
            print("")
            print("Cancelled. No files were changed.")
            print(f"Report JSON: {report_path}")
            return 0

    moved: list[SanitizeItem] = []
    deleted: list[SanitizeItem] = []
    if action == "quarantine":
        moved = quarantine_items(scan["items"], input_root, quarantine_dir)
        final_action = "quarantined"
    elif action == "delete":
        deleted = delete_items(scan["items"])
        final_action = "deleted"
    else:
        raise ValueError(f"Unsupported sanitize action: {action}")

    report = build_report(
        input_root=input_root,
        quarantine_dir=quarantine_dir,
        scan=scan,
        action=final_action,
        moved=moved,
        deleted=deleted,
        cancelled=False,
        elapsed_seconds=time.time() - started,
    )
    write_report(report_path, report)
    print_final_report(report_path, report)
    return 0


def _ensure_cursor_visible() -> None:
    if not sys.stderr.isatty():
        return
    try:
        sys.stderr.write("\033[?25h")
        sys.stderr.flush()
    except Exception:
        pass


def validate_input_root(input_root: Path, quarantine_dir: Path) -> str | None:
    if not input_root.exists():
        return f"Input directory does not exist: {input_root}"
    if not input_root.is_dir():
        return f"Input path is not a directory: {input_root}"
    if input_root == Path("/"):
        return "Refusing to sanitize the filesystem root."
    home = Path.home().resolve()
    if input_root == home:
        return "Refusing to sanitize the home directory root."
    if quarantine_dir == input_root or input_root in quarantine_dir.parents:
        return "Quarantine directory must not be the same as the source root or nested inside it."
    return None


def resolve_action(value: str) -> str:
    return value.strip().lower()


def _safe_tty_input(prompt: str) -> str:
    """Input() that tolerates misconfigured TTYs where Enter sends \\r (CR) instead of \\n (NL).

    In a normal cooked TTY, the line discipline translates CR->NL (stty icrnl), so input()
    works. If that translation is disabled (e.g. stty -icrnl), input() can appear to hang
    because it waits for \\n. We temporarily enable ICRNL while reading the line.
    """
    if not sys.stdin.isatty():
        return input(prompt)
    try:
        import termios

        fd = sys.stdin.fileno()
        original = termios.tcgetattr(fd)
        updated = original[:]
        updated[0] = int(updated[0]) | int(termios.ICRNL)
        termios.tcsetattr(fd, termios.TCSADRAIN, updated)
        return input(prompt)
    except Exception:
        return input(prompt)
    finally:
        try:
            import termios

            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, original)  # type: ignore[name-defined]
        except Exception:
            pass


def prompt_for_action() -> str:
    while True:
        choice = _safe_tty_input("Choose action: [q]uarantine, [d]elete, [c]ancel: ").strip().lower()
        if choice in {"q", "quarantine"}:
            return "quarantine"
        if choice in {"d", "delete"}:
            return "delete"
        if choice in {"c", "cancel"}:
            return "cancel"
        print("Please enter quarantine, delete, or cancel.")


def confirm_delete(scan: dict[str, object]) -> bool:
    removable_count = int(scan["removable_count"])
    removable_bytes = int(scan["removable_bytes"])
    expected = "DELETE"
    response = _safe_tty_input(
        f"Type {expected} to permanently remove {removable_count} files ({format_gb(removable_bytes)}): "
    ).strip()
    return response == expected


def default_quarantine_dir(input_root: Path) -> Path:
    return input_root.parent / f"{input_root.name}__quarantine"


def scan_sanitization_candidates(
    input_root: Path,
    demo_min_seconds: float = DEMO_MIN_SECONDS_DEFAULT,
    mix_min_seconds: float = MIX_MIN_SECONDS_DEFAULT,
    song_min_seconds: float = SONG_MIN_SECONDS_DEFAULT,
    remove_unopenable_audio: bool = False,
    workers: int = 1,
) -> dict[str, object]:
    items: list[SanitizeItem] = []
    probe_requests: list[_ProbeRequest] = []
    suspicious_counts: Counter[str] = Counter()
    suspicious_bytes: Counter[str] = Counter()
    suspicious_examples: list[dict[str, object]] = []
    kept_supported = 0
    kept_supported_bytes = 0
    total_bytes = 0

    progress = get_progress_bar()
    all_files: list[Path] = []
    for dirpath, _, filenames in os.walk(input_root):
        base = Path(dirpath)
        for name in filenames:
            all_files.append(base / name)

    iterator: object = all_files
    if progress is not None and all_files:
        iterator = progress(all_files, total=len(all_files), desc="Scanning files", unit="file", mininterval=0.5)

    for path in iterator:  # type: ignore[assignment]
        size = file_size(path)
        total_bytes += size
        removable, probe = classify_sanitize_item(
            input_root,
            path,
            size,
            demo_min_seconds=demo_min_seconds,
            mix_min_seconds=mix_min_seconds,
            song_min_seconds=song_min_seconds,
            remove_unopenable_audio=remove_unopenable_audio,
        )
        if removable is not None:
            items.append(removable)
            continue
        if probe is not None:
            probe_requests.append(probe)
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            kept_supported += 1
            kept_supported_bytes += size

    def record_suspicious(match: str, req: _ProbeRequest, duration: float | None, openable: bool | None) -> None:
        suspicious_counts[match] += 1
        suspicious_bytes[match] += req.bytes
        if len(suspicious_examples) >= SUSPICIOUS_EXAMPLE_LIMIT:
            return
        suspicious_examples.append(
            {
                "match": match,
                "relative_path": req.relative_path,
                "path": str(req.path),
                "extension": req.extension,
                "bytes": req.bytes,
                "duration_seconds": duration,
                "openable": openable,
            }
        )

    if probe_requests:
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
            futures = {pool.submit(ffprobe_audio_info, req.path): req for req in probe_requests}
            probe_iter: object = as_completed(futures)
            if progress is not None:
                probe_iter = progress(
                    probe_iter,
                    total=len(futures),
                    desc="Probing audio",
                    unit="file",
                    mininterval=0.5,
                )
            for future in probe_iter:  # type: ignore[assignment]
                req = futures[future]
                duration, openable = future.result()
                if req.wants_openable_check and not openable:
                    items.append(
                        SanitizeItem(
                            path=str(req.path),
                            relative_path=req.relative_path,
                            extension=req.extension,
                            bytes=req.bytes,
                            reason="unopenable_audio",
                        )
                    )
                    continue
                if req.wants_demo_check and duration is not None and duration > float(demo_min_seconds):
                    items.append(
                        SanitizeItem(
                            path=str(req.path),
                            relative_path=req.relative_path,
                            extension=req.extension,
                            bytes=req.bytes,
                            reason="demo_long_audio",
                        )
                    )
                    continue
                if req.wants_mix_check and duration is not None and duration > float(mix_min_seconds):
                    items.append(
                        SanitizeItem(
                            path=str(req.path),
                            relative_path=req.relative_path,
                            extension=req.extension,
                            bytes=req.bytes,
                            reason="mix_long_audio",
                        )
                    )
                    continue
                if req.wants_song_check and duration is not None and duration > float(song_min_seconds):
                    items.append(
                        SanitizeItem(
                            path=str(req.path),
                            relative_path=req.relative_path,
                            extension=req.extension,
                            bytes=req.bytes,
                            reason="song_long_audio",
                        )
                    )
                    continue
                if req.wants_demo_check:
                    record_suspicious(
                        "demo_kept_short_or_unknown",
                        req,
                        duration,
                        openable if req.wants_openable_check else None,
                    )
                elif req.wants_mix_check:
                    record_suspicious(
                        "mix_kept_short_or_unknown",
                        req,
                        duration,
                        openable if req.wants_openable_check else None,
                    )
                elif req.wants_song_check:
                    record_suspicious(
                        "song_or_track_kept_short_or_unknown",
                        req,
                        duration,
                        openable if req.wants_openable_check else None,
                    )
                kept_supported += 1
                kept_supported_bytes += req.bytes

    reason_counts = Counter(item.reason for item in items)
    extension_counts = Counter(item.extension for item in items)
    reason_bytes = Counter()
    extension_bytes = Counter()
    for item in items:
        reason_bytes[item.reason] += item.bytes
        extension_bytes[item.extension] += item.bytes

    return {
        "scanned_files": len(all_files),
        "total_bytes": total_bytes,
        "kept_supported_files": kept_supported,
        "kept_supported_bytes": kept_supported_bytes,
        "removable_count": len(items),
        "removable_bytes": sum(item.bytes for item in items),
        "items": items,
        "suspicious_count": int(sum(suspicious_counts.values())),
        "suspicious_bytes": int(sum(suspicious_bytes.values())),
        "suspicious_by_match": [
            {"match": match, "count": suspicious_counts[match], "bytes": suspicious_bytes[match]}
            for match, _ in suspicious_counts.most_common()
        ],
        "suspicious_examples": suspicious_examples,
        "by_reason": [
            {"reason": reason, "count": reason_counts[reason], "bytes": reason_bytes[reason]}
            for reason, _ in reason_counts.most_common()
        ],
        "by_extension": [
            {"extension": extension, "count": extension_counts[extension], "bytes": extension_bytes[extension]}
            for extension, _ in extension_counts.most_common()
        ],
        "examples": [asdict(item) for item in items[:20]],
    }


def classify_sanitize_item(
    input_root: Path,
    path: Path,
    size: int,
    *,
    demo_min_seconds: float = DEMO_MIN_SECONDS_DEFAULT,
    mix_min_seconds: float = MIX_MIN_SECONDS_DEFAULT,
    song_min_seconds: float = SONG_MIN_SECONDS_DEFAULT,
    remove_unopenable_audio: bool = False,
) -> tuple[SanitizeItem | None, _ProbeRequest | None]:
    extension = normalized_extension(path)
    relative = str(path.relative_to(input_root))
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        reason = unsupported_reason(path, extension)
        return (
            SanitizeItem(
                path=str(path),
                relative_path=relative,
                extension=extension,
                bytes=size,
                reason=reason,
            ),
            None,
        )
    stem_text = normalized_name_text(path.stem)
    if any(pattern in stem_text for pattern in normalized_patterns()):
        return (
            SanitizeItem(
                path=str(path),
                relative_path=relative,
                extension=extension,
                bytes=size,
                reason="ignored_name_pattern",
            ),
            None,
        )
    wants_demo = is_demo_name(stem_text)
    wants_mix = is_mix_name(stem_text)
    wants_song = is_song_name(stem_text)
    wants_openable = bool(remove_unopenable_audio)
    if not wants_demo and not wants_mix and not wants_song and not wants_openable:
        return None, None
    return (
        None,
        _ProbeRequest(
            path=path,
            relative_path=relative,
            extension=extension,
            bytes=size,
            wants_demo_check=wants_demo,
            wants_mix_check=wants_mix,
            wants_song_check=wants_song,
            wants_openable_check=wants_openable,
        ),
    )


def unsupported_reason(path: Path, extension: str) -> str:
    name = path.name
    lowered = name.lower()
    if lowered == ".ds_store" or lowered.startswith("._"):
        return "mac_artifact"
    if lowered == "icon" and extension == "[no extension]":
        return "mac_artifact"
    if extension in PACK_BAGGAGE_EXTENSIONS:
        return "pack_baggage"
    stem = normalized_name_text(path.stem)
    if "readme" in stem or "license" in stem or "credits" in stem:
        return "pack_baggage"
    return "unsupported_file"


def get_progress_bar():
    if not sys.stderr.isatty():
        return None
    try:
        from tqdm import tqdm  # type: ignore
    except Exception:
        return None
    return tqdm


def normalized_patterns() -> tuple[str, ...]:
    return tuple(normalized_name_text(pattern) for pattern in IGNORED_NAME_PATTERNS)


def normalized_name_text(value: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in value.lower()).split())


def is_demo_name(normalized_stem_text: str) -> bool:
    # normalized_stem_text is already lowercase and whitespace-separated.
    # We match the token 'demo' and variants like 'demo01' / 'demo1' (common in sample packs).
    for token in normalized_stem_text.split():
        if token == "demo":
            return True
        if token.startswith("demo") and token[4:].isdigit():
            return True
    return False


def is_song_name(normalized_stem_text: str) -> bool:
    for token in normalized_stem_text.split():
        if token in {"song", "track"}:
            return True
        if token.startswith("song") and token[4:].isdigit():
            return True
        if token.startswith("track") and token[5:].isdigit():
            return True
    return False


def is_mix_name(normalized_stem_text: str) -> bool:
    # "mix" by itself is extremely common in pack loop names (e.g. "perc mix") and
    # would create a ton of unnecessary duration probes. Instead, only flag mix-like
    # names that are strongly associated with full arrangements.
    if "mixdown" in normalized_stem_text:
        return True
    if "final mix" in normalized_stem_text:
        return True

    for token in normalized_stem_text.split():
        # Patterns like "clubmix01", "extendedmix2", etc.
        for prefix in ("clubmix", "extendedmix", "originalmix", "radiomix"):
            if token.startswith(prefix) and token[len(prefix) :].isdigit():
                return True
        for prefix in ("mixdown", "finalmix"):
            if token.startswith(prefix) and token[len(prefix) :].isdigit():
                return True
    return False


def ffprobe_duration_seconds(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=10)
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout or "{}")
    except Exception:
        return None
    streams = payload.get("streams") or []
    stream = streams[0] if streams else {}
    duration = stream.get("duration") or (payload.get("format") or {}).get("duration")
    try:
        return float(duration) if duration is not None else None
    except (TypeError, ValueError):
        return None


def ffprobe_audio_openable(path: Path) -> bool:
    """
    Best-effort check for "is this supported audio file actually readable".
    We deliberately use ffprobe only: if it can't see an audio stream, KeyFinder/ffmpeg likely won't either.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=10)
    except Exception:
        return False
    if completed.returncode != 0:
        return False
    try:
        payload = json.loads(completed.stdout or "{}")
    except Exception:
        return False
    streams = payload.get("streams") or []
    return bool(streams)


def ffprobe_audio_info(path: Path) -> tuple[float | None, bool]:
    """Return (duration_seconds, openable) from a single ffprobe invocation."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None, True
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=10)
    except Exception:
        return None, False
    if completed.returncode != 0:
        return None, False
    try:
        payload = json.loads(completed.stdout or "{}")
    except Exception:
        return None, False
    streams = payload.get("streams") or []
    openable = any(stream.get("codec_type") == "audio" for stream in streams if isinstance(stream, dict))
    duration = None
    try:
        fmt = payload.get("format") or {}
        raw = fmt.get("duration")
        if raw is not None:
            duration = float(raw)
    except Exception:
        duration = None
    return duration, bool(openable)


def normalized_extension(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if suffix else "[no extension]"


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def quarantine_items(items: list[SanitizeItem], input_root: Path, quarantine_dir: Path) -> list[SanitizeItem]:
    moved: list[SanitizeItem] = []
    progress = get_progress_bar()
    iterator: object = items
    if progress is not None and items:
        iterator = progress(items, total=len(items), desc="Quarantining", unit="file", mininterval=0.5)
    for item in iterator:  # type: ignore[assignment]
        source = Path(item.path)
        destination = quarantine_dir / Path(item.relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved.append(item)
    return moved


def delete_items(items: list[SanitizeItem]) -> list[SanitizeItem]:
    deleted: list[SanitizeItem] = []
    progress = get_progress_bar()
    iterator: object = items
    if progress is not None and items:
        iterator = progress(items, total=len(items), desc="Deleting", unit="file", mininterval=0.5)
    for item in iterator:  # type: ignore[assignment]
        path = Path(item.path)
        if path.exists():
            path.unlink()
        deleted.append(item)
    return deleted


def build_report(
    *,
    input_root: Path,
    quarantine_dir: Path,
    scan: dict[str, object],
    action: str,
    moved: list[SanitizeItem],
    deleted: list[SanitizeItem],
    cancelled: bool,
    elapsed_seconds: float,
) -> dict[str, object]:
    remaining_bytes = sum(file_size(path) for path in input_root.rglob("*") if path.is_file())
    affected = moved if action == "quarantined" else deleted
    affected_reason_counts = Counter(item.reason for item in affected)
    affected_reason_bytes = Counter()
    affected_extension_counts = Counter(item.extension for item in affected)
    affected_extension_bytes = Counter()
    for item in affected:
        affected_reason_bytes[item.reason] += item.bytes
        affected_extension_bytes[item.extension] += item.bytes
    examples_by_reason: list[dict[str, object]] = []
    for reason, _ in affected_reason_counts.most_common():
        if len(examples_by_reason) >= 10:
            break
        example_paths: list[str] = []
        for item in affected:
            if item.reason != reason:
                continue
            example_paths.append(item.relative_path)
            if len(example_paths) >= 5:
                break
        examples_by_reason.append({"reason": reason, "examples": example_paths})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_root": str(input_root),
        "quarantine_dir": str(quarantine_dir),
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "ignored_name_patterns": list(IGNORED_NAME_PATTERNS),
        "action": action,
        "cancelled": cancelled,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "scan": {
            key: value
            for key, value in scan.items()
            if key != "items"
        },
        "before": {
            "files": int(scan["scanned_files"]),
            "bytes": int(scan["total_bytes"]),
        },
        "after": {
            "bytes": remaining_bytes,
        },
        "affected": {
            "count": len(affected),
            "bytes": sum(item.bytes for item in affected),
            "by_reason": [
                {"reason": reason, "count": affected_reason_counts[reason], "bytes": affected_reason_bytes[reason]}
                for reason, _ in affected_reason_counts.most_common()
            ],
            "examples_by_reason": examples_by_reason,
            "by_extension": [
                {
                    "extension": extension,
                    "count": affected_extension_counts[extension],
                    "bytes": affected_extension_bytes[extension],
                }
                for extension, _ in affected_extension_counts.most_common()
            ],
            "items": [asdict(item) for item in affected],
        },
    }


def print_pre_action_report(input_root: Path, scan: dict[str, object]) -> None:
    print("Sanitization scan:")
    print(f"  Source root: {input_root}")
    print(f"  Files scanned: {scan['scanned_files']}")
    print(f"  Supported audio kept: {scan['kept_supported_files']} files ({format_gb(int(scan['kept_supported_bytes']))})")
    print(f"  Removable files: {scan['removable_count']} files ({format_gb(int(scan['removable_bytes']))})")
    print("")
    print("Supported audio formats kept:")
    print(f"  {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    print("")
    print("Removable by reason:")
    for item in scan["by_reason"][:10]:
        print(f"  - {item['reason']}: {item['count']} files ({format_gb(int(item['bytes']))})")
    print("Removable by extension:")
    for item in scan["by_extension"][:10]:
        print(f"  - {item['extension']}: {item['count']} files ({format_gb(int(item['bytes']))})")
    if scan["examples"]:
        print("Examples:")
        for item in scan["examples"][:10]:
            print(f"  - {item['reason']} | {item['relative_path']}")
    suspicious_by_match = scan.get("suspicious_by_match") or []
    if suspicious_by_match:
        print("")
        print("Kept but suspicious (matched demo/mix/song/track heuristics, but kept as short/unknown):")
        for item in suspicious_by_match[:8]:
            print(f"  - {item['match']}: {item['count']} files ({format_gb(int(item['bytes']))})")
        suspicious_examples = scan.get("suspicious_examples") or []
        if suspicious_examples:
            print("Examples:")
            for item in suspicious_examples[:8]:
                print(f"  - {item.get('match')} | {item.get('relative_path')}")


def print_final_report(report_path: Path, report: dict[str, object]) -> None:
    print("")
    print("Sanitization result:")
    print(f"  Action: {report['action']}")
    print(f"  Files affected: {report['affected']['count']} files")
    print(f"  Size removed/moved: {format_gb(int(report['affected']['bytes']))}")
    print(f"  Size remaining in source: {format_gb(int(report['after']['bytes']))}")
    if report["affected"]["by_reason"]:
        print("  Affected by reason:")
        for item in report["affected"]["by_reason"][:5]:
            print(f"    - {item['reason']}: {item['count']} files ({format_gb(int(item['bytes']))})")
    if report["affected"]["by_extension"]:
        print("  Affected by extension:")
        for item in report["affected"]["by_extension"][:5]:
            print(f"    - {item['extension']}: {item['count']} files ({format_gb(int(item['bytes']))})")
    examples_by_reason = report["affected"].get("examples_by_reason") or []
    if examples_by_reason:
        print("  Examples by reason:")
        for item in examples_by_reason[:5]:
            examples = item.get("examples") or []
            if not examples:
                continue
            joined = "; ".join(str(path) for path in examples[:3])
            print(f"    - {item.get('reason')}: {joined}")
    if report["action"] == "quarantined":
        print(f"  Quarantine folder: {report['quarantine_dir']}")
    print(f"  Report JSON: {report_path}")


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def format_gb(bytes_count: int) -> str:
    return f"{bytes_count / 1_000_000_000:.2f} GB"


if __name__ == "__main__":
    raise SystemExit(main())
