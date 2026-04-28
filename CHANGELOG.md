# Changelog

## 0.4.0 (V4)

- V4 deep analysis pipeline (routed, resumable, batch-safe):
  - Essentia tonal context (key/root/HPCP + chord hints), tuning frequency, loop BPM + ticks.
  - Monophonic note events via Essentia pitch contour segmentation.
  - Polyphonic note events via Basic Pitch where routing calls for it.
  - Confidence fusion + per-backend breakdown stored in the index.
- Kitchen sink improvements:
  - One-command index + KeyFinder enrich + optional deep analysis.
  - Timing summary written to `analysis_run_report.json`.
  - Resumable KeyFinder and deep-analysis passes (skip up-to-date work).
- Sanitization improvements:
  - Fast scan progress + optional ffprobe openability checks with `--remove-unopenable-audio`.
  - Removes pack baggage (docs/artwork/readmes), Mac artifacts, full-arrangement mixes, long demos/songs/tracks.
  - Compact "kept but suspicious" rollups for demo/mix/song/track names that were kept.
- Web app improvements:
  - Multi-library loading in chunks with progress feedback.
  - Better selection UX (scroll/highlight) and detail-fetch loading/errors.
  - AIFF/AIF playback reliability improvements (server transcode + metadata preload).
  - Review state toggling stored back to SQLite.
- Security:
  - Optional LAN binding hardening (`--allow-ip`, `--allow-cidr`, `--auth-token`).

