from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sample_key_indexer.models import AnalysisResult, file_signature


class MetadataIndex:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.records: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            self.records = {_record_path(record): record for record in data}
        else:
            self.records = {_record_path(record): record for record in data.get("files", [])}

    def should_skip(self, path: Path, force: bool = False) -> bool:
        if force:
            return False
        record = self.records.get(str(path))
        if not record:
            return False
        signature = file_signature(path)
        record_size, record_mtime = _record_signature(record)
        return record_size == signature["size"] and record_mtime == signature["mtime"]

    def upsert(self, result: AnalysisResult) -> None:
        self.records[result.file_path] = result.to_dict()

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 2, "schema": "sample-key-indexer.v1", "files": sorted(self.records.values(), key=_record_path)}
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temp_path.replace(self.path)


def _record_path(record: dict[str, Any]) -> str:
    file_block = record.get("file")
    if isinstance(file_block, dict):
        return str(file_block.get("path", ""))
    return str(record.get("file_path", ""))


def _record_signature(record: dict[str, Any]) -> tuple[int | None, float | None]:
    file_block = record.get("file")
    if isinstance(file_block, dict):
        return file_block.get("size"), file_block.get("mtime")
    return record.get("size"), record.get("mtime")
