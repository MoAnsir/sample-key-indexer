from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import shutil
import time
from pathlib import Path

from sample_key_indexer.discovery import SUPPORTED_EXTENSIONS

IGNORED_NAME_PATTERNS: tuple[str, ...] = (
    "fullmix",
    "full mix",
    "musicloop",
    "music loop",
)


@dataclass(frozen=True)
class SanitizeItem:
    path: str
    relative_path: str
    extension: str
    bytes: int
    reason: str


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_root = args.input_root.expanduser().resolve()
    report_path = (args.report_json or (input_root / "sanitize_report.json")).expanduser().resolve()
    quarantine_dir = default_quarantine_dir(input_root) if args.quarantine_dir is None else args.quarantine_dir.expanduser().resolve()

    validation_error = validate_input_root(input_root, quarantine_dir)
    if validation_error:
        print(validation_error)
        return 2

    started = time.time()
    scan = scan_sanitization_candidates(input_root)
    print_pre_action_report(input_root, scan)

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


def prompt_for_action() -> str:
    while True:
        choice = input("Choose action: [q]uarantine, [d]elete, [c]ancel: ").strip().lower()
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
    response = input(
        f"Type {expected} to permanently remove {removable_count} files ({format_gb(removable_bytes)}): "
    ).strip()
    return response == expected


def default_quarantine_dir(input_root: Path) -> Path:
    return input_root.parent / f"{input_root.name}__quarantine"


def scan_sanitization_candidates(input_root: Path) -> dict[str, object]:
    all_files = sorted(path for path in input_root.rglob("*") if path.is_file())
    items: list[SanitizeItem] = []
    kept_supported = 0
    kept_supported_bytes = 0
    total_bytes = 0
    for path in all_files:
        size = file_size(path)
        total_bytes += size
        removable = classify_sanitize_item(input_root, path, size)
        if removable is None:
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                kept_supported += 1
                kept_supported_bytes += size
            continue
        items.append(removable)

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


def classify_sanitize_item(input_root: Path, path: Path, size: int) -> SanitizeItem | None:
    extension = normalized_extension(path)
    relative = str(path.relative_to(input_root))
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return SanitizeItem(
            path=str(path),
            relative_path=relative,
            extension=extension,
            bytes=size,
            reason="unsupported_file",
        )
    stem_text = normalized_name_text(path.stem)
    if any(pattern in stem_text for pattern in normalized_patterns()):
        return SanitizeItem(
            path=str(path),
            relative_path=relative,
            extension=extension,
            bytes=size,
            reason="ignored_name_pattern",
        )
    return None


def normalized_patterns() -> tuple[str, ...]:
    return tuple(normalized_name_text(pattern) for pattern in IGNORED_NAME_PATTERNS)


def normalized_name_text(value: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in value.lower()).split())


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
    for item in items:
        source = Path(item.path)
        destination = quarantine_dir / Path(item.relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved.append(item)
    return moved


def delete_items(items: list[SanitizeItem]) -> list[SanitizeItem]:
    deleted: list[SanitizeItem] = []
    for item in items:
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
