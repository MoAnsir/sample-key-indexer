from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
        choices=("all", "missing"),
        default="all",
        help="KeyFinder enrich scope after indexing. Default: all.",
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


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Parse only our wrapper args; everything else is passed to sample-key-indexer.
    parser = build_parser()
    known, passthrough = parser.parse_known_args(argv)
    input_root = known.input_root
    output_root = known.output_root

    index_args = [str(input_root), str(output_root)] + passthrough
    index_rc = index_cli.main(index_args)
    if index_rc != 0:
        return index_rc

    sqlite_path = output_root / "metadata_index.sqlite"
    if not sqlite_path.exists():
        print(f"Expected index not found: {sqlite_path}")
        return 2

    library_id = _infer_library_id(passthrough, output_root)
    default_json = Path("/tmp") / f"{library_id}_keyfinder_enrich.json"
    keyfinder_json = (known.keyfinder_json or default_json).expanduser().resolve()

    review_args: list[str] = [
        str(sqlite_path),
        "--keyfinder-enrich",
        "--keyfinder-scope",
        known.keyfinder_scope,
        "--keyfinder-workers",
        str(int(known.keyfinder_workers)),
        "--write-every",
        str(known.keyfinder_write_every),
        "--keyfinder-json",
        str(keyfinder_json),
    ]
    if known.keyfinder_convert_retry:
        review_args.append("--keyfinder-convert-retry")

    return review_report.main(review_args)


if __name__ == "__main__":
    raise SystemExit(main())
