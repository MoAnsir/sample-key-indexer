from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sample_key_indexer.index_store import SQLiteMetadataIndex, load_records
from sample_key_indexer.models import AnalysisResult


class SQLiteMetadataIndexTests(unittest.TestCase):
    def test_sqlite_index_upserts_and_exports_json_records(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "kick.wav"
            audio_path.write_bytes(b"audio")
            index_path = root / "metadata_index.sqlite"
            json_path = root / "metadata_index.json"
            result = AnalysisResult(
                file_path=str(audio_path),
                root_note="C",
                key="C_major",
                confidence=0.8,
                category="OneShots",
                type="Kick",
                duration=0.4,
                size=audio_path.stat().st_size,
                mtime=audio_path.stat().st_mtime,
                analysis_profile="balanced",
                analysis_engines=["librosa", "essentia"],
            )

            index = SQLiteMetadataIndex(index_path)
            try:
                index.upsert(result)
                index.write()

                self.assertTrue(index.should_skip(audio_path))
                index.export_json(json_path)
            finally:
                index.close()

            records = load_records(json_path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["analysis"]["profile"], "balanced")
            self.assertEqual(records[0]["analysis"]["engines"], ["librosa", "essentia"])

    def test_load_records_reads_sqlite_directly(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_path = root / "bass.wav"
            audio_path.write_bytes(b"audio")
            index_path = root / "metadata_index.sqlite"
            result = AnalysisResult(
                file_path=str(audio_path),
                root_note="A",
                key="A_minor",
                confidence=0.7,
                category="OneShots",
                type="Bass",
                duration=0.8,
                size=audio_path.stat().st_size,
                mtime=audio_path.stat().st_mtime,
            )

            index = SQLiteMetadataIndex(index_path)
            try:
                index.upsert(result)
                index.write()
            finally:
                index.close()

            records = load_records(index_path)
            self.assertEqual(records[0]["file"]["path"], str(audio_path))
            self.assertEqual(records[0]["musical"]["key"], "A_minor")


if __name__ == "__main__":
    unittest.main()
