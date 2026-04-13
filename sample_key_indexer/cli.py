from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from sample_key_indexer.discovery import discover_audio_files
from sample_key_indexer.index_store import MetadataIndex
from sample_key_indexer.routing import route_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index and organise audio samples by detected key/root note.")
    parser.add_argument("input_root", type=Path, help="Root directory containing .wav, .mp3, .aiff, or .aif files.")
    parser.add_argument("output_root", type=Path, help="Directory where the organised library and metadata will be written.")
    parser.add_argument("--workers", type=int, default=max(1, min(4, os.cpu_count() or 1)), help="Parallel analysis workers.")
    parser.add_argument("--analysis-duration", type=float, default=30.0, help="Max seconds loaded per file.")
    parser.add_argument("--sample-rate", type=int, default=22050, help="Analysis sample rate.")
    parser.add_argument("--index-file", type=Path, default=None, help="Metadata JSON path. Defaults to output_root/metadata_index.json.")
    parser.add_argument("--force", action="store_true", help="Reprocess files already present in the metadata index.")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying them.")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and update destinations in metadata without copying/moving files.")
    parser.add_argument("--write-every", type=int, default=100, help="Write metadata after this many processed files.")
    parser.add_argument("--doctor", action="store_true", help="Check the local audio-analysis environment and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from tqdm import tqdm
    except ModuleNotFoundError:
        tqdm = lambda iterable, **_: iterable

    from sample_key_indexer.audio_analysis import analyze_file, validate_audio_backend

    try:
        validate_audio_backend()
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
        return 0

    input_root = args.input_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    index_path = (args.index_file or output_root / "metadata_index.json").expanduser().resolve()
    index = MetadataIndex(index_path)

    files = discover_audio_files(input_root)
    pending = [path for path in files if not index.should_skip(path, force=args.force)]
    print(f"Discovered {len(files)} audio files; {len(pending)} pending.")

    processed = 0
    if pending:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(analyze_file, path, args.analysis_duration, args.sample_rate): path
                for path in pending
            }
            for future in tqdm(as_completed(futures), total=len(futures), unit="file"):
                result = future.result()
                routed = route_file(result, output_root, move=args.move, dry_run=args.dry_run)
                index.upsert(routed)
                processed += 1
                if processed % max(1, args.write_every) == 0:
                    index.write()

    index.write()
    print(f"Indexed {processed} files. Metadata: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
