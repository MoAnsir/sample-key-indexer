from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sample_key_indexer.sanitize import (
    build_report,
    classify_sanitize_item,
    default_quarantine_dir,
    delete_items,
    main,
    normalized_name_text,
    quarantine_items,
    scan_sanitization_candidates,
)


class SanitizeTests(unittest.TestCase):
    def test_normalized_name_text_flattens_separator_variants(self) -> None:
        self.assertEqual(normalized_name_text("music-loop_demo"), "music loop demo")
        self.assertEqual(normalized_name_text("fullmix"), "fullmix")

    def test_classify_sanitize_item_flags_unsupported_and_ignored_names(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsupported = root / "Pack" / "loop.rx2"
            unsupported.parent.mkdir()
            unsupported.write_bytes(b"1")
            readme = root / "Pack" / "ReadMe.txt"
            readme.write_bytes(b"hello")
            artwork = root / "Pack" / "Cover.jpg"
            artwork.write_bytes(b"jpg")
            ds_store = root / ".DS_Store"
            ds_store.write_bytes(b"ds")
            fullmix = root / "Pack" / "song_fullmix.wav"
            fullmix.write_bytes(b"12")
            musicloop = root / "Pack" / "artist_music-loop_demo.wav"
            musicloop.write_bytes(b"123")

            unsupported_item = classify_sanitize_item(root, unsupported, unsupported.stat().st_size)
            readme_item = classify_sanitize_item(root, readme, readme.stat().st_size)
            artwork_item = classify_sanitize_item(root, artwork, artwork.stat().st_size)
            ds_store_item = classify_sanitize_item(root, ds_store, ds_store.stat().st_size)
            fullmix_item = classify_sanitize_item(root, fullmix, fullmix.stat().st_size)
            musicloop_item = classify_sanitize_item(root, musicloop, musicloop.stat().st_size)

        self.assertEqual(unsupported_item.reason, "unsupported_file")
        self.assertEqual(readme_item.reason, "pack_baggage")
        self.assertEqual(artwork_item.reason, "pack_baggage")
        self.assertEqual(ds_store_item.reason, "mac_artifact")
        self.assertEqual(fullmix_item.reason, "ignored_name_pattern")
        self.assertEqual(musicloop_item.reason, "ignored_name_pattern")

    def test_classify_sanitize_item_flags_demo_long_audio_only_when_over_threshold(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo = root / "Pack" / "demo01.wav"
            demo.parent.mkdir()
            demo.write_bytes(b"not real audio")

            with patch("sample_key_indexer.sanitize.ffprobe_duration_seconds", return_value=61.0):
                item = classify_sanitize_item(root, demo, demo.stat().st_size, demo_min_seconds=60.0)
            self.assertIsNotNone(item)
            self.assertEqual(item.reason, "demo_long_audio")

            with patch("sample_key_indexer.sanitize.ffprobe_duration_seconds", return_value=59.0):
                item2 = classify_sanitize_item(root, demo, demo.stat().st_size, demo_min_seconds=60.0)
            self.assertIsNone(item2)

    def test_scan_sanitization_candidates_summarizes_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.wav").write_bytes(b"audio")
            (root / "Pack" / "bad.mid").parent.mkdir()
            (root / "Pack" / "bad.mid").write_bytes(b"midi")
            (root / "Pack" / "ReadMe.txt").write_bytes(b"readme")
            (root / "Pack" / "song full mix.wav").write_bytes(b"mix")
            (root / "Pack" / "artist_musicloop_demo.wav").write_bytes(b"loop")

            scan = scan_sanitization_candidates(root)

        self.assertEqual(scan["scanned_files"], 5)
        self.assertEqual(scan["kept_supported_files"], 1)
        self.assertEqual(scan["removable_count"], 4)
        reasons = {item["reason"]: item["count"] for item in scan["by_reason"]}
        self.assertEqual(reasons["unsupported_file"], 1)
        self.assertEqual(reasons["ignored_name_pattern"], 2)
        self.assertEqual(reasons["pack_baggage"], 1)

    def test_quarantine_items_preserves_relative_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            quarantine = Path(tmp) / "quarantine"
            path = root / "Pack" / "song_fullmix.wav"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"mix")
            scan = scan_sanitization_candidates(root)

            moved = quarantine_items(scan["items"], root, quarantine)

            self.assertEqual(len(moved), 1)
            self.assertFalse(path.exists())
            self.assertTrue((quarantine / "Pack" / "song_fullmix.wav").exists())

    def test_delete_items_removes_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "bad.mid"
            path.write_bytes(b"midi")
            item = classify_sanitize_item(root, path, path.stat().st_size)

            deleted = delete_items([item])

            self.assertEqual(len(deleted), 1)
            self.assertFalse(path.exists())

    def test_default_quarantine_dir_is_sibling(self) -> None:
        root = Path("/tmp/source")
        self.assertEqual(default_quarantine_dir(root), Path("/tmp/source__quarantine"))

    def test_build_report_includes_all_affected_items(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.mid").write_bytes(b"midi")
            scan = scan_sanitization_candidates(root)
            report = build_report(
                input_root=root,
                quarantine_dir=default_quarantine_dir(root),
                scan=scan,
                action="dry_run",
                moved=[],
                deleted=[],
                cancelled=False,
                elapsed_seconds=1.5,
            )

        self.assertEqual(report["scan"]["removable_count"], 1)
        self.assertEqual(report["affected"]["count"], 0)
        self.assertEqual(report["supported_extensions"], [".aif", ".aiff", ".mp3", ".wav"])

    def test_main_dry_run_writes_report_without_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            (root / "bad.mid").write_bytes(b"midi")
            report_path = root / "sanitize_report.json"

            code = main([str(root), "--dry-run"])

            self.assertEqual(code, 0)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["action"], "dry_run")
            self.assertTrue((root / "bad.mid").exists())

    def test_main_quarantine_action_moves_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            bad = root / "bad.mid"
            bad.write_bytes(b"midi")
            quarantine = Path(tmp) / "keep"

            code = main([str(root), "--action", "quarantine", "--quarantine-dir", str(quarantine)])

            self.assertEqual(code, 0)
            self.assertFalse(bad.exists())
            self.assertTrue((quarantine / "bad.mid").exists())

    def test_main_delete_requires_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            bad = root / "bad.mid"
            bad.write_bytes(b"midi")

            with patch("builtins.input", return_value="DELETE"):
                code = main([str(root), "--action", "delete"])

            self.assertEqual(code, 0)
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
