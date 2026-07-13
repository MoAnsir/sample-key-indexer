from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sample_key_indexer.index_store import SQLiteMetadataIndex
from sample_key_indexer.sketch import validate_sketch_payload
from sample_key_indexer.sketch_store import (
    SKETCH_LIBRARY_ID,
    SKETCH_PATH_PREFIX,
    delete_sketch,
    get_sketch,
    list_sketches,
    save_sketch,
    sketch_record,
)
from sample_key_indexer.web_app import _playback_info, load_samples, summarize_libraries


def valid_sketch(**overrides):
    payload = {
        "name": "MPC bass idea",
        "tonic": "Eb",
        "mode": "minor",
        "bpm": 140,
        "bars": 8,
        "type": "Bass",
        "notes": ["Eb", "Gb", "Bb"],
    }
    payload.update(overrides)
    sketch, errors = validate_sketch_payload(payload)
    assert errors == [], errors
    return sketch


class SketchRecordTests(unittest.TestCase):
    def test_record_shape(self) -> None:
        record = sketch_record(valid_sketch())
        self.assertTrue(record["file_path"].startswith(SKETCH_PATH_PREFIX))
        self.assertEqual(record["library_id"], SKETCH_LIBRARY_ID)
        self.assertEqual(record["library_name"], "Sketches")
        self.assertEqual(record["source_kind"], "sketch")
        self.assertEqual(record["key"], "D#_minor")
        self.assertIn("created_at", record)
        self.assertTrue(record["sketch_id"])

    def test_unique_ids(self) -> None:
        first = sketch_record(valid_sketch())
        second = sketch_record(valid_sketch())
        self.assertNotEqual(first["sketch_id"], second["sketch_id"])

    def test_explicit_id_reused(self) -> None:
        record = sketch_record(valid_sketch(), sketch_id="abc123")
        self.assertEqual(record["sketch_id"], "abc123")
        self.assertEqual(record["file_path"], f"{SKETCH_PATH_PREFIX}abc123")


class SketchStoreRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.store = Path(self._tmp.name) / "sketches.sqlite"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_save_and_list(self) -> None:
        saved = save_sketch(valid_sketch(), path=self.store)
        records = list_sketches(self.store)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["sketch_id"], saved["sketch_id"])
        self.assertEqual(records[0]["name"], "MPC bass idea")

    def test_save_multiple(self) -> None:
        save_sketch(valid_sketch(name="one"), path=self.store)
        save_sketch(valid_sketch(name="two"), path=self.store)
        names = {r["name"] for r in list_sketches(self.store)}
        self.assertEqual(names, {"one", "two"})

    def test_update_in_place_with_same_id(self) -> None:
        saved = save_sketch(valid_sketch(name="before"), path=self.store)
        save_sketch(valid_sketch(name="after", bpm=160), path=self.store, sketch_id=saved["sketch_id"])
        records = list_sketches(self.store)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "after")
        self.assertEqual(records[0]["bpm"], 160)

    def test_get_sketch(self) -> None:
        saved = save_sketch(valid_sketch(), path=self.store)
        found = get_sketch(saved["sketch_id"], path=self.store)
        self.assertIsNotNone(found)
        self.assertEqual(found["sketch_id"], saved["sketch_id"])
        self.assertIsNone(get_sketch("nope", path=self.store))

    def test_delete_sketch(self) -> None:
        saved = save_sketch(valid_sketch(), path=self.store)
        self.assertTrue(delete_sketch(saved["sketch_id"], path=self.store))
        self.assertEqual(list_sketches(self.store), [])

    def test_delete_missing_returns_false(self) -> None:
        save_sketch(valid_sketch(), path=self.store)
        self.assertFalse(delete_sketch("does-not-exist", path=self.store))
        self.assertEqual(len(list_sketches(self.store)), 1)

    def test_list_missing_store_returns_empty(self) -> None:
        self.assertEqual(list_sketches(Path(self._tmp.name) / "absent.sqlite"), [])

    def test_delete_missing_store_returns_false(self) -> None:
        self.assertFalse(delete_sketch("any", path=Path(self._tmp.name) / "absent.sqlite"))


class SQLiteDeleteRecordTests(unittest.TestCase):
    def test_delete_record(self) -> None:
        with TemporaryDirectory() as tmp:
            index = SQLiteMetadataIndex(Path(tmp) / "index.sqlite")
            index.upsert_record({"file_path": "/a.wav", "size": 1, "mtime": 1.0})
            index.write()
            self.assertTrue(index.delete_record("/a.wav"))
            self.assertFalse(index.delete_record("/a.wav"))
            index.write()
            self.assertEqual(index.records(), [])
            index.close()


class SketchWebIntegrationTests(unittest.TestCase):
    def test_playback_info_marks_sketches(self) -> None:
        record = sketch_record(valid_sketch())
        info = _playback_info(record)
        self.assertEqual(info["status"], "sketch")
        self.assertEqual(info["source"], "sketch")

    def test_load_samples_includes_sketches_index(self) -> None:
        with TemporaryDirectory() as tmp:
            store = Path(tmp) / "sketches.sqlite"
            save_sketch(valid_sketch(), path=store)
            samples = load_samples([store])
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]["library_id"], SKETCH_LIBRARY_ID)
            self.assertEqual(samples[0]["playback_status"], "sketch")
            self.assertEqual(samples[0]["source_kind"], "sketch")

    def test_sketches_summarized_as_library(self) -> None:
        with TemporaryDirectory() as tmp:
            store = Path(tmp) / "sketches.sqlite"
            save_sketch(valid_sketch(name="one"), path=store)
            save_sketch(valid_sketch(name="two"), path=store)
            samples = load_samples([store])
            libraries = summarize_libraries(samples)
            self.assertEqual(len(libraries), 1)
            self.assertEqual(libraries[0]["id"], SKETCH_LIBRARY_ID)
            self.assertEqual(libraries[0]["total"], 2)


if __name__ == "__main__":
    unittest.main()
