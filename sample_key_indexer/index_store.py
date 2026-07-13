from __future__ import annotations

import json
from pathlib import Path
import sqlite3
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


class SQLiteMetadataIndex:
    def __init__(self, path: Path, json_seed_path: Path | None = None) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._migrate()
        if json_seed_path and json_seed_path.exists() and self._record_count() == 0:
            self._import_json(json_seed_path)

    def close(self) -> None:
        self.connection.close()

    def should_skip(self, path: Path, force: bool = False) -> bool:
        if force:
            return False
        row = self.connection.execute(
            "select size, mtime from samples where path = ?",
            (str(path),),
        ).fetchone()
        if not row:
            return False
        signature = file_signature(path)
        return row["size"] == signature["size"] and row["mtime"] == signature["mtime"]

    def upsert(self, result: AnalysisResult) -> None:
        record = result.to_dict()
        self.upsert_record(record)

    def upsert_record(self, record: dict[str, Any]) -> None:
        path = _record_path(record)
        size, mtime = _record_signature(record)
        self.connection.execute(
            """
            insert into samples (path, size, mtime, payload)
            values (?, ?, ?, ?)
            on conflict(path) do update set
                size = excluded.size,
                mtime = excluded.mtime,
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP
            """,
            (path, size, mtime, json.dumps(record, sort_keys=True)),
        )

    def write(self) -> None:
        self.connection.commit()

    def delete_record(self, path: str) -> bool:
        cursor = self.connection.execute("delete from samples where path = ?", (path,))
        return cursor.rowcount > 0

    def export_json(self, path: Path) -> None:
        self.write()
        records = self.records()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 3, "schema": "sample-key-indexer.v2", "files": records}
        temp_path = path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temp_path.replace(path)

    def records(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("select payload from samples order by path").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def _migrate(self) -> None:
        self.connection.execute(
            """
            create table if not exists samples (
                path text primary key,
                size integer,
                mtime real,
                payload text not null,
                updated_at text not null default CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.execute(
            """
            create table if not exists index_meta (
                key text primary key,
                value text not null
            )
            """
        )
        self.connection.execute(
            "insert or replace into index_meta (key, value) values (?, ?)",
            ("schema", "sample-key-indexer.v2"),
        )
        self.connection.commit()

    def _record_count(self) -> int:
        row = self.connection.execute("select count(*) as count from samples").fetchone()
        return int(row["count"])

    def _import_json(self, path: Path) -> None:
        seed = MetadataIndex(path)
        for record in seed.records.values():
            self.upsert_record(record)
        self.write()


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        index = SQLiteMetadataIndex(path)
        try:
            return index.records()
        finally:
            index.close()
    index = MetadataIndex(path)
    return sorted(index.records.values(), key=_record_path)


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
