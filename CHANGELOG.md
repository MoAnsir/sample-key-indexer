# Changelog

## Unreleased (V5 — Tests)

- Frontend test suite added:
  - **Unit tests** (Vitest + React Testing Library + MSW): 48 tests across `useReviewFiltering`, the API client, `applyFilters`/`sortSamples` in the Zustand store, and the Dashboard component (including the delete confirm/cancel flow). MSW intercepts all `fetch` calls so tests run without a backend.
  - **E2E tests** (Playwright + Chromium): catalog load, filter bar, delete-library flow, and scan wizard; all API calls mocked via `page.route()` so no Python backend is needed. Playwright auto-starts the Vite dev server.
  - New npm scripts: `npm test`, `npm run test:watch`, `npm run test:coverage`, `npm run test:e2e`, `npm run test:e2e:ui`.

## Unreleased (V5 — Scan from Web UI)

- Web UI can now run a full scan without the CLI:
  - Server-side folder browser endpoint (`/api/browse-folders`) — the browser's native file picker can't return absolute filesystem paths, so folder selection walks the filesystem via the backend instead.
  - Scan wizard (source → mode → destination → options → progress → done) supporting catalog-only or organize mode, configurable worker count, and live phase/progress/log streaming.
  - New library appears on the dashboard automatically on completion — no manual page refresh or backend restart required.
  - "Remove library & delete scan data" action on dashboard cards deletes index files, the run report, and organized `Key`/`Unsorted` folders, and reloads the backend's in-memory state so the card disappears immediately.
  - Known scan locations persist to `~/.sample-key-indexer/scan_history.json` and auto-load on `sample-key-indexer-web` startup.
- Core indexer (`cli.py`) analysis loop now processes files in batches of 50 instead of submitting the entire library to one worker pool. A crashing worker now only loses its current batch (retried file-by-file in isolated mode) instead of the rest of the run.
- Fixed a backend bug where the in-memory list of loaded index paths only ever grew, never shrank — meaning a deleted index could still be reloaded and would silently recreate an empty `.sqlite` file via `sqlite3.connect()`. `load_samples` now skips any index path that no longer exists on disk.
- Review diagnostics panel in the sample detail view now starts collapsed.

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

