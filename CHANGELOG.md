# Changelog

## Unreleased (V5 — Sketches)

Analyze musical ideas without an audio file — describe what you played on the MPC and get the same analysis scanned samples get.

- **Sketch analysis API** (`POST /api/sketch/analyze`): converts a user-entered sketch (key, mode, BPM, bars, type, frequency register, notes or full note events) into the same sample shape the audio pipeline produces and runs it through `build_musical_context()` — key, mood, compatible keys, progressions, transitions, plus out-of-scale note detection. Flats normalize to sharps; note tokens accept names ("Eb", "d#2") and MIDI numbers.
- **MIDI generation**: `POST /api/sketch/midi` renders entered note events (beats → seconds via BPM, embedded tempo + time signature) to a standard `.mid`; `GET /api/sketch/midi?sketch_id=…` does the same from a stored sketch.
- **Persistence**: sketches save to `~/.sample-key-indexer/sketches.sqlite` (same index format as scanned libraries), auto-load on startup, and appear in the catalog as a `sketches` library. Save/delete reload in-memory state so the UI updates instantly.
- **Sketch editor UI** (full page, not a popup — with a step indicator and ← Library back button):
  - Details form with MPC-style flat/sharp key labels, minor/major toggle, BPM/bars/beats-per-bar, all 17 sample types, frequency register
  - **Piano-roll grid modeled on the MPC Grid View**: Pencil/Eraser/Select tools (click add, drag move, edge resize, double-click erase, shift multi-select), Pad Perform-style scale row filtering with red root rows and Chromatic toggle, T.C. divisions `1/4 · 4 steps/bar` → `1/64 · 64 steps/bar` incl. triplets with Absolute/Relative/Off snap, live step gridlines, per-note velocity lane (single scrollbar synced with the grid), Transpose ±1 / Duplicate / octave shift / Clear
  - Full results view: summary chips, played notes vs scale notes, compatible keys with diatonic chords, progressions with roman numerals and mood badges, transition reasoning, out-of-scale warnings, and MIDI download of exactly what you played
- **Dashboard & table integration**: the Sketches library renders as a distinct ✏ card (dashed accent border, "N sketches", no misleading "missing" warning, no scan-data delete — sketches are removed individually); table rows show a ✏ Sketch status badge with inline ⬇ MIDI and ✕ delete actions.
- Tests: 24 new backend tests (analysis, validation, MIDI round trips, persistence), 34 new frontend unit tests, and an 11-test Playwright e2e suite covering the whole flow (create → notes → analyze → save → card → table actions → delete).

## Unreleased (V5 — CI)

- GitHub Actions CI workflow added (`.github/workflows/ci.yml`):
  - Triggers on every pull request to `dev` or `main`, and on every push to `dev`.
  - **Backend job**: `pytest tests/` on Python 3.11 and 3.12 (matrix). Excludes `test_audio_analysis.py` which requires native audio libs (librosa/essentia) not available on CI runners — those tests remain part of the local test suite.
  - **Frontend unit job**: TypeScript type-check (`tsc`) + Vitest run (48 tests). Runs independently so type errors and test failures are reported separately.
  - **E2E job**: Playwright/Chromium suite, gated on the unit job passing. Uploads `playwright-report/` as an artifact (7-day retention) on failure so screenshots are available in the Actions tab.
  - All three jobs must pass before a PR can be merged.

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

