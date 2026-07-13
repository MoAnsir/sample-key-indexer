"""Persistence for user-entered sketches.

Sketches are stored in the same SQLite index format as scanned samples
(`~/.sample-key-indexer/sketches.sqlite` by default), so the web app can
load them alongside scanned libraries. Each record is a flat sample dict
with a synthetic `sketch://<id>` path — there is no audio file on disk.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sample_key_indexer.index_store import SQLiteMetadataIndex
from sample_key_indexer.sketch import sketch_to_sample

SKETCH_LIBRARY_ID = "sketches"
SKETCH_LIBRARY_NAME = "Sketches"
SKETCH_PATH_PREFIX = "sketch://"


def default_sketches_path() -> Path:
    return Path.home() / ".sample-key-indexer" / "sketches.sqlite"


def sketch_record(sketch: dict[str, Any], sketch_id: str | None = None) -> dict[str, Any]:
    """Build the index record for a validated sketch."""
    record = sketch_to_sample(sketch)
    record["sketch_id"] = sketch_id or uuid.uuid4().hex
    record["file_path"] = f"{SKETCH_PATH_PREFIX}{record['sketch_id']}"
    record["library_id"] = SKETCH_LIBRARY_ID
    record["library_name"] = SKETCH_LIBRARY_NAME
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    return record


def save_sketch(sketch: dict[str, Any], path: Path | None = None, sketch_id: str | None = None) -> dict[str, Any]:
    """Persist a validated sketch; returns the stored record.

    Passing an existing sketch_id updates that sketch in place.
    """
    store_path = path or default_sketches_path()
    index = SQLiteMetadataIndex(store_path)
    try:
        record = sketch_record(sketch, sketch_id)
        index.upsert_record(record)
        index.write()
        return record
    finally:
        index.close()


def list_sketches(path: Path | None = None) -> list[dict[str, Any]]:
    store_path = path or default_sketches_path()
    if not store_path.exists():
        return []
    index = SQLiteMetadataIndex(store_path)
    try:
        return index.records()
    finally:
        index.close()


def get_sketch(sketch_id: str, path: Path | None = None) -> dict[str, Any] | None:
    for record in list_sketches(path):
        if record.get("sketch_id") == sketch_id:
            return record
    return None


def delete_sketch(sketch_id: str, path: Path | None = None) -> bool:
    store_path = path or default_sketches_path()
    if not store_path.exists():
        return False
    index = SQLiteMetadataIndex(store_path)
    try:
        deleted = index.delete_record(f"{SKETCH_PATH_PREFIX}{sketch_id}")
        index.write()
        return deleted
    finally:
        index.close()
