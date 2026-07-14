# sample-key-indexer

## What it does

A local audio sample library tool that scans audio files, detects musical key/BPM/timbre, classifies samples by type, and presents them through a React web UI. Users can browse/filter their sample catalog, play audio, download MIDI chord progressions, review low-confidence analyses, and create "sketches" — manually described musical ideas (key, BPM, notes entered in an MPC-style piano roll) that receive the same key/mood/progression analysis as scanned samples.

## Architecture

Two independently runnable layers:

**Python backend** (`sample_key_indexer/`)
- Stdlib `http.server.ThreadingHTTPServer` — no web framework. All routes in `web_app.py`.
- Analysis pipeline: `audio_analysis.py` → `classify.py` → `routing.py` → `index_store.py`
- Index stored as either JSON (`metadata_index.json`) or SQLite (`metadata_index.sqlite`). SQLite is preferred and is the only writable format for review state mutations.
- Five CLI entry points (see `pyproject.toml` `[project.scripts]`).

**React frontend** (`web/`)
- Vite + React + TypeScript. State managed by Zustand (`web/src/store/useAppStore.ts`).
- Data fetching via TanStack Query. API client at `web/src/api/client.ts`.
- Dev: `web/dist/` is served by the Python server when built; falls back to `sample_key_indexer/web_static/` (legacy).
- Unit tests: Vitest + React Testing Library + MSW (`web/src/test/mocks/`).
- E2E tests: Playwright/Chromium (`web/e2e/`); all API calls mocked via `page.route()` — no Python backend needed.

**CI** (`.github/workflows/ci.yml`)
- Triggers on PRs to `main`/`dev` and pushes to `dev`.
- Three jobs must all pass before a PR can merge:
  1. **Backend** — `pytest` on Python 3.11 and 3.12 (matrix). `test_audio_analysis.py` is excluded (requires native audio libs not available on runners).
  2. **Frontend** — TypeScript type-check (`tsc`) + Vitest.
  3. **E2E** — Playwright/Chromium, gated on the frontend job. Uploads `playwright-report/` as an artifact (7-day retention) on failure.

## Key files

| File | Purpose |
|---|---|
| `sample_key_indexer/models.py` | `AnalysisResult` dataclass — the canonical shape for one analyzed sample |
| `sample_key_indexer/audio_analysis.py` | Core analysis: librosa (always), essentia (optional), key detection, MFCCs, BPM |
| `sample_key_indexer/classify.py` | Heuristic classification of samples into category/type/subtype |
| `sample_key_indexer/index_store.py` | `MetadataIndex` (JSON) and `SQLiteMetadataIndex` — read/write/upsert |
| `sample_key_indexer/web_app.py` | HTTP server, all REST routes, sample flattening, audio streaming with range support |
| `sample_key_indexer/music_theory.py` | `build_musical_context()`, chord progressions, MIDI generation for samples |
| `sample_key_indexer/sketch.py` | "Sketch" feature — validate/analyze sketch payloads, MIDI generation for note events |
| `sample_key_indexer/sketch_store.py` | CRUD for sketches (persisted to `~/.sample-key-indexer/sketches.sqlite`); auto-loaded on startup |
| `sample_key_indexer/scan_manager.py` | Background scan job lifecycle; scan history persisted to `~/.sample-key-indexer/scan_history.json` |
| `web/src/components/SketchWizard.tsx` | Full-page sketch editor: details form + piano-roll grid + results view |
| `web/src/components/PianoRoll.tsx` | MPC Grid View–style piano roll: Pencil/Eraser/Select tools, scale row filtering, T.C. divisions, velocity lane |
| `web/src/lib/piano-roll.ts` | Piano-roll state logic: note CRUD, snap, duration quantization (pure, tested separately) |
| `web/src/components/SketchResults.tsx` | Sketch analysis results: played notes, compatible keys, progressions, transitions, MIDI download |
| `sample_key_indexer/routing.py` | Decides destination path for organized-copy mode |
| `sample_key_indexer/cli.py` | `sample-key-indexer` CLI — scan + organize, parallel with `ProcessPoolExecutor` |
| `web/src/App.tsx` | Root component: tab nav, library loading, scan/sketch wizard triggers |
| `web/src/store/useAppStore.ts` | Global Zustand store: samples, filters, active tab, theme |
| `web/src/types/api.ts` | TypeScript types matching the Python JSON API exactly |

## API routes

`GET /api/catalog` — summary counts + library list  
`GET /api/samples` — paginated slim sample list (offset/limit/library_id)  
`GET /api/sample?id=N` — full sample detail including musical context  
`GET /api/audio?id=N` — audio bytes with range support; AIF/AIFF transcoded via ffmpeg  
`GET /api/sample-midi?id=N&progression=N` — MIDI download for a chord progression  
`GET /api/browse-folders` — server-side filesystem walker for the scan wizard folder picker  
`GET /api/scan/status` / `GET /api/scan/history`  
`GET /api/sketches` — list all saved sketches  
`GET /api/sketch/midi?sketch_id=X` — download MIDI for a saved sketch  
`POST /api/scan/start` — start a background scan (catalog or organize mode)  
`POST /api/scan/add-index` / `POST /api/scan/remove` / `POST /api/scan/delete-data`  
`POST /api/review` — toggle reviewed flag (SQLite indexes only)  
`POST /api/sketch/analyze` — analyze a sketch payload, return musical context  
`POST /api/sketch/midi` — render entered note events to `.mid` bytes  
`POST /api/sketch/save` / `POST /api/sketch/delete`  
`POST /api/reload` — reload index from disk  

## Conventions

- **Python**: `from __future__ import annotations` in every module. Frozen dataclasses for immutable data (`AnalysisResult`, `AudioProbe`). Type hints throughout.
- **Index format**: JSON index records use a nested schema (`file`, `musical`, `audio_features`, `classification`, `analysis`, `routing`). `web_app._flatten_sample()` collapses this into a flat dict for the API.
- **Analysis engines**: `"fast"` profile = librosa only; `"balanced"/"deep"` = librosa + essentia. Engine list stored on each record.
- **Playback resolution**: Four fallback levels tried in order — organized stored path → organized mounted root → source stored path → source mounted root (relative path + library root).
- **React state**: All samples are loaded client-side into Zustand and filtered in-memory (`web/src/utils/filters.ts`). The IndexedDB sample cache (`web/src/lib/sample-cache.ts`) enables instant load on revisit.
- **Auth**: Optional IP allowlist (`--allow-ip`/`--allow-cidr`) and bearer token (`--auth-token` / `X-SKI-Token` header). Non-loopback bind requires at least one guard.
- **Sketch storage**: `~/.sample-key-indexer/sketches.sqlite` (same index format as scanned libraries). On `sample-key-indexer-web` startup, this file and all paths from `scan_history.json` are auto-loaded alongside any CLI-supplied indexes.
- **Scan-from-web**: the scan wizard (`ScanWizard.tsx`) uses `/api/browse-folders` for folder selection (the browser's native file picker can't return absolute paths). Scans run as background threads; the wizard polls `/api/scan/status` for progress. On completion the new library appears on the dashboard without a server restart. Known scan locations persist to `~/.sample-key-indexer/scan_history.json`.
- **Dashboard sketch cards**: the Sketches library renders as a distinct ✏ card (dashed border, no "missing" warning, no delete-scan-data action). Table rows for sketches show a ✏ badge with inline MIDI download and delete.
- **Tests**: Python tests in `tests/` use pytest and write real temp files (no mocking of the index). `test_audio_analysis.py` requires native audio libs and is excluded from CI. Frontend unit tests use Vitest + MSW. E2E tests mock all API responses via `page.route()` and auto-start the Vite dev server via Playwright's `webServer` config.

## Running

```bash
# Install (editable)
pip install -e .

# Scan a directory and write an index
sample-key-indexer /path/to/Samples --output /path/to/index/

# Start the web UI
sample-key-indexer-web /path/to/index/metadata_index.sqlite

# Run frontend dev server (separate terminal)
cd web && npm run dev

# Build frontend for production (served by the Python server)
cd web && npm run build

# Python tests (excludes audio-engine tests that need librosa/essentia locally)
pytest
pytest tests/ --ignore=tests/test_audio_analysis.py  # CI-equivalent subset

# Frontend unit tests (Vitest)
cd web && npm test           # single run
cd web && npm run test:watch # watch mode
cd web && npm run test:coverage

# Type check
cd web && npm run type-check

# E2E tests (no backend needed — Playwright starts Vite automatically)
cd web && npm run test:e2e
cd web && npm run test:e2e:ui  # interactive UI mode
```
