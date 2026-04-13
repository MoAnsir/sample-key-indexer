from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif"}


def discover_audio_files(root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Input directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {root}")

    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return sorted(files)
