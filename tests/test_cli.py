from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from sample_key_indexer.cli import split_long_files


class CliTests(unittest.TestCase):
    def test_split_long_files_skips_above_threshold(self) -> None:
        paths = [Path("short.wav"), Path("song.wav"), Path("unknown.wav")]
        durations = {
            Path("short.wav"): 12.0,
            Path("song.wav"): 180.0,
            Path("unknown.wav"): None,
        }

        with patch("sample_key_indexer.audio_analysis.quick_audio_duration", side_effect=lambda path: durations[path]):
            processable, skipped = split_long_files(paths, 60.0)

        self.assertEqual(processable, [Path("short.wav"), Path("unknown.wav")])
        self.assertEqual(skipped, [Path("song.wav")])

    def test_split_long_files_can_be_disabled(self) -> None:
        paths = [Path("song.wav")]
        processable, skipped = split_long_files(paths, 0)

        self.assertEqual(processable, paths)
        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
