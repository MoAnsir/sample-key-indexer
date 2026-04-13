from __future__ import annotations

from dataclasses import replace
import shutil
from pathlib import Path

from sample_key_indexer.models import AnalysisResult

DRUM_ONESHOT_TYPES = {"Kick", "Snare", "Hat", "Perc"}


def destination_for(result: AnalysisResult, output_root: Path) -> Path:
    category_path = _category_path(result)
    if result.key_or_root:
        return output_root / "Key" / result.key_or_root / category_path / Path(result.file_path).name
    return output_root / "Unsorted" / category_path / Path(result.file_path).name


def route_file(result: AnalysisResult, output_root: Path, move: bool = False, dry_run: bool = False) -> AnalysisResult:
    source = Path(result.file_path)
    destination = destination_for(result, output_root)
    if not dry_run:
        destination = _dedupe_path(destination)
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if move:
            shutil.move(str(source), str(destination))
        else:
            shutil.copy2(source, destination)
    return replace(result, destination=str(destination))


def _dedupe_path(destination: Path) -> Path:
    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}__{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _category_path(result: AnalysisResult) -> Path:
    if result.category == "OneShots" and result.type in DRUM_ONESHOT_TYPES:
        return Path(result.category) / "Drums" / result.type
    return Path(result.category) / result.type
