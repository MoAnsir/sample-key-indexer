from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import time

from sample_key_indexer import cli as index_cli
from sample_key_indexer import review_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run sample-key-indexer, then enrich the resulting index with KeyFinder (one-command kitchen sink).",
        add_help=True,
        allow_abbrev=False,
    )
    parser.add_argument("input_root", type=Path, help="Source samples root (passed to sample-key-indexer).")
    parser.add_argument("output_root", type=Path, help="Output root (passed to sample-key-indexer).")
    parser.add_argument(
        "--keyfinder-scope",
        choices=("missing", "all", "review", "failures"),
        default="missing",
        help="KeyFinder enrich scope after indexing. Default: missing (resumable).",
    )
    parser.add_argument(
        "--keyfinder-force",
        action="store_true",
        help="Rerun KeyFinder even if a successful result is already stored (only affects --keyfinder-scope missing).",
    )
    parser.add_argument(
        "--keyfinder-convert-retry",
        action="store_true",
        help="Allow ffmpeg conversion retry for KeyFinder when direct decoding fails.",
    )
    parser.add_argument(
        "--keyfinder-json",
        type=Path,
        default=None,
        help="Write KeyFinder enrich report JSON. Default: /tmp/<library_id>_keyfinder_enrich.json",
    )
    parser.add_argument(
        "--keyfinder-write-every",
        type=int,
        default=25,
        help="SQLite write frequency during KeyFinder enrich. Default: 25.",
    )
    parser.add_argument(
        "--keyfinder-workers",
        type=int,
        default=1,
        help="Parallelism for the KeyFinder enrich phase. Default: 1.",
    )
    parser.add_argument(
        "--deep-analysis",
        choices=("off", "smart", "force-all"),
        default="off",
        help="Plan Melodyne-style deep-analysis routing after KeyFinder. Default: off.",
    )
    parser.add_argument(
        "--deep-analysis-scope",
        choices=("missing", "review", "musical", "all"),
        default="missing",
        help="Which samples to include in deep-analysis planning. Default: missing.",
    )
    parser.add_argument(
        "--deep-analysis-json",
        type=Path,
        default=None,
        help="Write the deep-analysis planning report JSON. Default: /tmp/<library_id>_deep_analysis.json",
    )
    parser.add_argument(
        "--",
        dest="passthrough_marker",
        action="store_true",
        help="All following args are passed through to sample-key-indexer.",
    )
    return parser


def _infer_library_id(passthrough: list[str], output_root: Path) -> str:
    for i, arg in enumerate(passthrough):
        if arg == "--library-id" and i + 1 < len(passthrough):
            return passthrough[i + 1]
    return output_root.name


def _infer_run_report_path(passthrough: list[str], output_root: Path) -> Path:
    for i, arg in enumerate(passthrough):
        if arg == "--report-json" and i + 1 < len(passthrough):
            return Path(passthrough[i + 1]).expanduser().resolve()
    return (output_root / "analysis_run_report.json").expanduser().resolve()


def _patch_run_report_with_keyfinder_rollups(run_report_path: Path, keyfinder_report_path: Path) -> None:
    if not run_report_path.exists() or not keyfinder_report_path.exists():
        return
    try:
        run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
        keyfinder_report = json.loads(keyfinder_report_path.read_text(encoding="utf-8"))
    except Exception:
        return
    offenders = run_report.get("offenders") or {}
    keyfinder = offenders.get("keyfinder") or {}
    # Keep it compact in JSON; terminal output already has details.
    if keyfinder_report.get("error_by_path_family"):
        keyfinder["error_by_path_family"] = list(keyfinder_report.get("error_by_path_family") or [])[:25]
    if keyfinder_report.get("error_codes"):
        keyfinder["error_codes"] = list(keyfinder_report.get("error_codes") or [])[:25]
    if keyfinder_report.get("error_reasons"):
        keyfinder["error_reasons"] = list(keyfinder_report.get("error_reasons") or [])[:25]
    offenders["keyfinder"] = keyfinder
    run_report["offenders"] = offenders
    try:
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        return


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Parse only our wrapper args; everything else is passed to sample-key-indexer.
    parser = build_parser()
    known, passthrough = parser.parse_known_args(argv)
    input_root = known.input_root
    output_root = known.output_root

    t0 = time.time()
    index_args = [str(input_root), str(output_root)] + passthrough
    index_rc = index_cli.main(index_args)
    if index_rc != 0:
        return index_rc
    t1 = time.time()

    sqlite_path = output_root / "metadata_index.sqlite"
    if not sqlite_path.exists():
        print(f"Expected index not found: {sqlite_path}")
        return 2

    library_id = _infer_library_id(passthrough, output_root)
    default_json = Path("/tmp") / f"{library_id}_keyfinder_enrich.json"
    keyfinder_json = (known.keyfinder_json or default_json).expanduser().resolve()
    deep_analysis_json = (known.deep_analysis_json or (Path("/tmp") / f"{library_id}_deep_analysis.json")).expanduser().resolve()

    review_args: list[str] = [
        str(sqlite_path),
        "--keyfinder-enrich",
        "--keyfinder-scope",
        known.keyfinder_scope,
        "--keyfinder-force" if known.keyfinder_force else "",
        "--keyfinder-workers",
        str(int(known.keyfinder_workers)),
        "--write-every",
        str(known.keyfinder_write_every),
        "--keyfinder-json",
        str(keyfinder_json),
    ]
    review_args = [arg for arg in review_args if arg]
    if known.keyfinder_convert_retry:
        review_args.append("--keyfinder-convert-retry")
    rc = review_report.main(review_args)
    t2 = time.time()
    deep_rc = 0
    if known.deep_analysis != "off":
        deep_args: list[str] = [
            str(sqlite_path),
            "--deep-analysis-plan",
            "--deep-analysis-mode",
            known.deep_analysis,
            "--deep-analysis-scope",
            known.deep_analysis_scope,
            "--write-every",
            str(known.keyfinder_write_every),
            "--deep-analysis-json",
            str(deep_analysis_json),
        ]
        deep_rc = review_report.main(deep_args)
    t3 = time.time()
    run_report_path = _infer_run_report_path(passthrough, output_root)
    _patch_run_report_with_keyfinder_rollups(run_report_path, keyfinder_json)
    if known.deep_analysis != "off":
        print(f"Kitchen sink timing: index {t1 - t0:.1f}s, keyfinder {t2 - t1:.1f}s, deep-plan {t3 - t2:.1f}s")
    else:
        print(f"Kitchen sink timing: index {t1 - t0:.1f}s, keyfinder {t2 - t1:.1f}s")
    return deep_rc or rc


if __name__ == "__main__":
    raise SystemExit(main())
