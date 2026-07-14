# Sample Library Key Indexer

You have thousands of audio samples — kicks, snares, bass hits, melody loops, pads, vocal chops — scattered across USB sticks, hard drives, and download folders. You're working on a track in A minor and need a bass loop that fits. Good luck finding one: your samples are buried in folders named things like `Pack_Vol3_Final_v2`, and you have no idea what key any of them are in.

**Sample Key Indexer** fixes this. Point it at any folder of samples and it will automatically:

- **Detect the musical key and root note** of every sample using multiple audio engines (librosa, essentia, KeyFinder, basic-pitch) cross-checked against each other
- **Classify each sample by type** — Kick, Snare, Hi-Hat, Bass, Lead, Pad, Chord, Melody Loop, Drum Loop, Vocal, FX, and 15+ categories — using filename patterns and audio feature analysis
- **Organize everything into clean folders by key and type** — all your A-minor bass loops in one place, all your E-major melody loops in another, drums sorted by kick/snare/hat
- **Build a rich metadata index** with root note, key, BPM, confidence scores, timbre, loudness, frequency features, and deep analysis for every single sample
- **Serve a web UI** for browsing, filtering, previewing, and reviewing your entire library from a browser — across multiple libraries and external drives

### See it in action

**Dashboard** — library overview with sample type breakdown and distribution charts:

![Dashboard](docs/screenshots/DashBoard.png)

**Browse** — search, filter by key/type/BPM/confidence, sort by any column, and preview audio inline:

![Browse](docs/screenshots/Browse.png)

**Sample Detail** — full analysis for any sample: detected key, notes, chords, frequency spectrum, MFCC timbre shape, compatible keys, chord progressions to try, and downloadable MIDI:

![Sample Detail](docs/screenshots/SampleDetails.png)

### Why use this?

- **Works at scale** — tested on 71,000+ samples across multiple libraries
- **Resumable** — crashes, USB disconnects, or running out of time? Pick up exactly where you left off
- **Catalog without copying** — index samples on a USB stick or external drive without duplicating any audio
- **Multi-library** — load indexes from multiple drives and browse them all in one UI
- **Deep analysis** — beyond just key detection: BPM, tuning (Hz), note transcription, onset detection, chord estimation, and confidence scoring across multiple engines
- **Fully local** — no cloud, no accounts, no subscriptions. Your samples and metadata stay on your machine

---

## Table of Contents

- [Install](#install)
- [Quick Start](#quick-start)
- [Starting the App Locally](#starting-the-app-locally)
- [Commands](#commands)
  - [sample-key-indexer](#sample-key-indexer--core-indexer)
  - [sample-key-indexer-kitchen-sink](#sample-key-indexer-kitchen-sink--all-in-one)
  - [sample-key-indexer-review](#sample-key-indexer-review--enrichment--verification)
  - [sample-key-indexer-web](#sample-key-indexer-web--web-browser-ui)
  - [sample-key-indexer-sanitize](#sample-key-indexer-sanitize--library-cleanup)
- [Output Structure](#output-structure)
- [Analysis Engines](#analysis-engines)
- [Web UI Guide](#web-ui-guide)
- [Workflows](#workflows)
- [Developing the Frontend](#developing-the-frontend)
- [CI / GitHub Actions](#ci--github-actions)
- [Troubleshooting](#troubleshooting)
- [Version History](#version-history)

---

## Install

```bash
cd /path/to/sample-key-indexer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### External Dependencies

These are not installable via pip and must be set up separately:

| Tool | Required? | Purpose |
|------|-----------|---------|
| **KeyFinder CLI** | Required | External key detection backend. Install and ensure `keyfinder-cli` or `keyfinder` is on `PATH`. |
| **ffprobe** / **ffmpeg** | Recommended | Fast duration probing, AIFF→WAV transcoding in web UI, conversion retry for KeyFinder failures. |
| **sonic-annotator** | Optional | Deep harmonic analysis (V4 deep-analysis routes). |
| **aubio** | Optional | Onset/tempo detection for deep analysis. |

Verify your setup:

```bash
sample-key-indexer /any/path /any/output --doctor
```

---

## Quick Start

### Path Placeholders

Throughout this guide, replace these placeholders with your actual folder paths:

| Placeholder | Meaning | Example |
|-------------|---------|---------|
| `/path/to/Samples` | The folder containing your source audio samples to be organized | `~/Music/MySamples`, `/Volumes/USB_01/Samples` |
| `/path/to/Output` or `/path/to/Organised` | Where samples are copied/moved to, organized into folders by musical key and sample type (e.g., `Key/A_minor/OneShots/Bass/`). See [Output Structure](#output-structure) | `~/Desktop/Samples_Organised` |
| `/path/to/Indexes/MY_LIBRARY` | Same as Output, but used with `--catalog-only` to store only the metadata index (no audio is copied). Useful for cataloging USB sticks or external drives — the web UI can then browse the index and stream audio from the original source via `--library-root` | `~/SampleIndexes/usb_01` |

### Commands

All commands below (e.g., `sample-key-indexer`, `sample-key-indexer-web`, `sample-key-indexer-kitchen-sink`) are CLI tools installed by `pip install -e .`. They are available in your terminal after activating the venv. Each one is a different tool for a different stage of the workflow — see the [Commands](#commands) section for full details.

### 1. Check your environment

```bash
sample-key-indexer ~/Music/MySamples ~/Desktop/Samples_Organised --doctor
```

### 2. Dry run (analyze without copying files)

```bash
sample-key-indexer ~/Music/MySamples ~/Desktop/Samples_Organised --dry-run
```

### 3. Organize your library

```bash
sample-key-indexer ~/Music/MySamples ~/Desktop/Samples_Organised
```

### 4. Browse in the web UI

```bash
sample-key-indexer-web ~/Desktop/Samples_Organised/metadata_index.sqlite
# Open http://127.0.0.1:8765 in your browser
```

See [Starting the App Locally](#starting-the-app-locally) for the full startup guide — including the one gotcha that catches everyone (a stale frontend build).

### 5. Full pipeline in one command

```bash
sample-key-indexer-kitchen-sink ~/Music/MySamples ~/SampleIndexes/my_library \
  --keyfinder-convert-retry --keyfinder-workers 8 \
  --deep-analysis smart --deep-analysis-scope musical
```

---

## Starting the App Locally

The app is two pieces: a **Python backend** (API + serves the UI) and a **React frontend**. There are two ways to run it — pick one.

### Option A — Production mode (one server, one URL)

The backend serves a pre-built copy of the frontend from `web/dist/`. Build it once, then start the backend:

```bash
# 1. Build the frontend (only needed after pulling new frontend code)
cd web
npm install          # first time only
npm run build        # writes web/dist/
cd ..

# 2. Start the backend
source .venv/bin/activate
sample-key-indexer-web ~/Desktop/Samples_Organised/metadata_index.sqlite
```

**Open: <http://127.0.0.1:8765>** — that's the whole app.

> ⚠️ **The stale-build gotcha:** the backend serves whatever is in `web/dist/` — it does NOT rebuild it for you. If you `git pull` new frontend features and don't rerun `npm run build`, you'll be looking at the old UI and wondering where the new feature went. When in doubt: `cd web && npm run build`, then hard-refresh the browser (Cmd+Shift+R).

Notes:
- Previously scanned libraries and saved sketches auto-load on startup — after the first scan you can start the server with any one index path (or a directory, which is searched for indexes).
- Use `--port 9000` to change the port, `--library-root ID=/path` to point playback at the original source audio.

### Option B — Development mode (live reload, two servers)

For working on the frontend. Run the backend and the Vite dev server side by side:

```bash
# Terminal 1 — backend API on :8765
source .venv/bin/activate
sample-key-indexer-web ~/Desktop/Samples_Organised/metadata_index.sqlite

# Terminal 2 — frontend dev server on :5173
cd web
npm run dev
```

**Open: <http://localhost:5173>** (not 8765). The dev server proxies all `/api/*` calls to the backend and hot-reloads the UI as you edit code. No build step needed — you always see the latest code.

| | URL | Frontend freshness |
|---|-----|--------------------|
| **Production mode** | http://127.0.0.1:8765 | Whatever `npm run build` last produced |
| **Development mode** | http://localhost:5173 | Always current, hot-reloads |

---

## Commands

### `sample-key-indexer` — Core Indexer

The main command. Scans audio files, analyzes them, classifies them, and optionally copies/moves them into an organized folder structure.

```bash
sample-key-indexer INPUT_ROOT OUTPUT_ROOT [options]
```

**Common flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | — | Analyze and update metadata without copying/moving files |
| `--catalog-only` | — | Write metadata index without organizing into Key/Unsorted folders |
| `--move` | — | Move files instead of copying |
| `--force` | — | Reprocess files already in the index |
| `--workers N` | auto (1–4) | Number of parallel analysis workers. Files are analyzed in batches of 50 — if a worker crashes, only that batch falls back to single-file isolated mode, so one bad file never loses the rest of the run |
| `--engines LIST` | balanced | Comma-separated engines: `librosa`, `essentia` |
| `--analysis-profile PROFILE` | balanced | Preset: `fast`, `balanced`, or `deep` |
| `--max-duration SECS` | 60 | Skip files longer than this (full songs) |
| `--include-long-files` | — | Don't skip long files |
| `--include-ignored-files` | — | Include fullmix/musicloop files normally skipped |
| `--library-id ID` | folder name | Stable ID for the source library |
| `--library-name NAME` | library ID | Human-readable display name |
| `--no-sqlite` | — | Use legacy JSON-only index |
| `--probe-backend MODE` | auto | Duration probe: `auto`, `ffprobe`, or `python` |
| `--doctor` | — | Check audio stack and exit |
| `--report-json PATH` | auto | Custom path for the JSON run report |

**Examples:**

```bash
# Catalog a USB stick without copying files
sample-key-indexer /Volumes/USB_01/Samples /path/to/Indexes/usb_01 \
  --catalog-only --library-id usb_01 --library-name "USB 01"

# Fast analysis with librosa only
sample-key-indexer /path/to/Samples /path/to/Output --analysis-profile fast

# Re-enrich an existing index with the latest feature schema
sample-key-indexer /path/to/Samples /path/to/Output --force --dry-run
```

---

### `sample-key-indexer-kitchen-sink` — All-in-One

Runs the full pipeline in one command: **index → KeyFinder enrich → deep analysis**.

```bash
sample-key-indexer-kitchen-sink INPUT_ROOT OUTPUT_ROOT [options] [-- passthrough-args]
```

Any arguments after `--` are passed through to the core indexer (e.g., `-- --workers 8 --dry-run`).

**KeyFinder options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--keyfinder-scope SCOPE` | missing | `missing`, `all`, `review`, or `failures` |
| `--keyfinder-force` | — | Rerun KeyFinder even if results exist |
| `--keyfinder-workers N` | 1 | Parallel KeyFinder workers |
| `--keyfinder-convert-retry` | — | Retry failures via ffmpeg WAV conversion |

**Deep-analysis options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--deep-analysis MODE` | off | `off`, `smart`, or `force-all` |
| `--deep-analysis-scope SCOPE` | missing | `missing`, `review`, `musical`, or `all` |

**Examples:**

```bash
# Index + KeyFinder only
sample-key-indexer-kitchen-sink /path/to/Samples /path/to/Indexes/MY_LIB \
  --keyfinder-convert-retry --keyfinder-workers 8

# Full pipeline with deep analysis on musical samples
sample-key-indexer-kitchen-sink /path/to/Samples /path/to/Indexes/MY_LIB \
  --keyfinder-convert-retry --keyfinder-workers 8 \
  --deep-analysis smart --deep-analysis-scope musical

# Pass extra flags to the core indexer
sample-key-indexer-kitchen-sink /path/to/Samples /path/to/Indexes/MY_LIB \
  --keyfinder-convert-retry -- --workers 4 --analysis-profile deep
```

---

### `sample-key-indexer-review` — Enrichment & Verification

Operates on an existing index. Used for KeyFinder enrichment, deep analysis, classification audits, and quality reports.

```bash
sample-key-indexer-review INDEX_DB [options]
```

**Modes:**

| Flag | Description |
|------|-------------|
| `--keyfinder-enrich` | Store KeyFinder results under `analysis.external.keyfinder` (doesn't change main key) |
| `--keyfinder-compare` | Read-only comparison of stored KeyFinder vs current key decisions |
| `--keyfinder-apply-review` | Flag high-confidence disagreements for review (doesn't change key) |
| `--deep-analysis-run` | Run V4 routed deep analysis |
| `--deep-plan` | Preview which samples would enter the deep-review queue |
| `--deep-rerun` | Reprocess only low-confidence/warning/error records |
| `--deep-failures` | Summarize files that failed deep review |
| `--classification-audit` | Scan for suspicious category/type decisions |
| `--backend-check` | Check availability of KeyFinder and optional deep backends |

**Examples:**

```bash
# Summary of files needing review
sample-key-indexer-review /path/to/metadata_index.sqlite

# KeyFinder enrichment across the full index
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --keyfinder-enrich --keyfinder-scope all --keyfinder-convert-retry

# Deep analysis on an existing index
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --deep-analysis-run --deep-analysis-mode smart --deep-analysis-scope musical \
  --library-root MY_LIB=/Volumes/USB/Samples

# Classification audit with examples
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --classification-audit --examples 50 \
  --classification-json /tmp/audit.json
```

---

### `sample-key-indexer-web` — Web Browser UI

A local web server for browsing, searching, and previewing your indexed sample libraries.

```bash
sample-key-indexer-web INDEX_PATHS [options]
# Then open http://127.0.0.1:8765
```

**Arguments:**
- One or more `.sqlite` / `.json` index files, or a directory to auto-discover indexes

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--host HOST` | 127.0.0.1 | Bind address |
| `--port PORT` | 8765 | Bind port |
| `--library-root LIB_ID=/path` | — | Override source audio root for playback (repeatable) |
| `--destination-root LIB_ID=/path` | — | Override organised output root for playback (repeatable) |
| `--allow-ip IP` | — | Restrict access to specific IPs (repeatable) |
| `--allow-cidr CIDR` | — | Restrict access to CIDR blocks (repeatable) |
| `--auth-token TOKEN` | — | Require token via header or query param |

**Features:**
- Browse samples by library, type, key, and BPM
- Play/preview audio inline (with automatic AIFF→WAV transcoding)
- Mark samples as reviewed (SQLite indexes only)
- View musical context: chords, progressions, MIDI generation
- Download MIDI progressions
- Multi-library: load multiple indexes at once
- LAN-safe: refuses non-loopback binding without access controls

**Examples:**

```bash
# Single index
sample-key-indexer-web /path/to/metadata_index.sqlite

# Multiple libraries with mounted USB playback
sample-key-indexer-web \
  /path/to/Indexes/USB_01/metadata_index.sqlite \
  /path/to/Indexes/SD_02/metadata_index.sqlite \
  --library-root usb_01=/Volumes/USB_01/Samples \
  --destination-root sd_02=/Volumes/SD_02/SAMPLEZ

# Auto-discover all indexes in a directory
sample-key-indexer-web /path/to/Indexes

# LAN access with auth
sample-key-indexer-web /path/to/metadata_index.sqlite \
  --host 0.0.0.0 --allow-cidr 192.168.1.0/24 --auth-token mysecret
```

**API endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /api/catalog` | Overall stats and library list |
| `GET /api/samples?library_id=X&offset=0&limit=50` | Paginated sample list |
| `GET /api/sample?id=X` | Full sample details with musical context |
| `GET /api/audio?id=X` | Stream audio (supports range requests) |
| `GET /api/sample-midi?id=X&progression=Y` | Generate and download MIDI |
| `POST /api/review` | Mark sample as reviewed/unreviewed |

---

### `sample-key-indexer-sanitize` — Library Cleanup

Scan a source library and remove unsupported files, pack baggage, Mac artifacts, full mixes, and demos before indexing.

```bash
sample-key-indexer-sanitize INPUT_ROOT [options]
```

Scans first, prints a removable-file report, then prompts for `quarantine`, `delete`, or `cancel`.

**Options:**

| Flag | Description |
|------|-------------|
| `--dry-run` | Inspect and write report without changing files |
| `--remove-unsupported` | Delete non-audio files |
| `--remove-long` | Delete tracks longer than threshold |
| `--remove-unopenable-audio` | Flag corrupt/unhandled audio that ffprobe cannot open |
| `--detect-demos` | Heuristic demo file detection |
| `--detect-mixes` | Heuristic full mix detection |
| `--detect-songs` | Heuristic full song detection |
| `--remove-detected` | Delete files flagged by detectors |

**Examples:**

```bash
# Preview what would be removed
sample-key-indexer-sanitize /path/to/Samples --dry-run

# Full cleanup including corrupt audio
sample-key-indexer-sanitize /path/to/Samples --remove-unopenable-audio
```

---

## Output Structure

After indexing, the organized library looks like this:

```
Output/
├── Key/
│   ├── A_minor/
│   │   ├── OneShots/
│   │   │   ├── Bass/
│   │   │   ├── Chords/
│   │   │   ├── Drums/ (Kick, Snare, Hat, Perc)
│   │   │   ├── FX/
│   │   │   ├── Leads/
│   │   │   ├── Pads/
│   │   │   ├── Plucks/
│   │   │   └── Vocals/
│   │   └── Loops/
│   │       ├── BassLoops/
│   │       ├── DrumLoops/
│   │       ├── FXLoops/
│   │       ├── MelodyLoops/
│   │       └── VocalLoops/
│   ├── B_major/
│   │   └── ...
│   └── ...
├── Unsorted/                  # Files with no detected key
├── metadata_index.sqlite      # V2 SQLite index (primary)
├── metadata_index.json        # JSON export
└── analysis_run_report.json   # Run stats and diagnostics
```

Each indexed sample stores structured metadata including:
- **file**: path, format, duration, sample rate, size
- **library**: source library ID and display name
- **musical**: root note, key, scale confidence, chord hints, BPM
- **audio_features**: loudness, frequency, timbre, MFCC averages
- **classification**: category, type, subtype, source, confidence
- **analysis**: per-engine decisions, warnings, final routing decision

---

## Analysis Engines

| Engine | Role |
|--------|------|
| **librosa** | Baseline pitch and chroma analysis (always available) |
| **essentia** | Key/scale analysis, tonal features, BPM, tuning (used in `balanced` profile) |
| **KeyFinder CLI** | External key detection stored as comparison signal |
| **basic-pitch** | Note event transcription for polyphonic deep-analysis routes |

The `--analysis-profile` flag selects engine combinations:
- **fast**: librosa only
- **balanced** (default): librosa + essentia
- **deep**: all available engines

---

## Web UI Guide

The web UI is a React + TypeScript single-page application that connects to the Python backend. Start both together:

```bash
# Terminal 1 — start the backend
sample-key-indexer-web ~/SampleIndexes/metadata_index.sqlite

# Terminal 2 — start the React dev server
cd web && npm run dev
# Open http://localhost:5173
```

Or for production (single server), build the frontend first:

```bash
cd web && npm run build
sample-key-indexer-web ~/SampleIndexes/metadata_index.sqlite
# Open http://127.0.0.1:8765
```

### Dashboard

When the app loads, you see the **Dashboard** — library cards and a sample type distribution chart.

- **Library cards** show each indexed library with total samples, available/missing counts
- **Click a card** to load that library's samples into the Browse tab
- **Remove library & delete scan data** (bottom of each card) deletes the index files (`metadata_index.sqlite`/`.json`), the run report, and any organized `Key/`/`Unsorted/` folders for that library. Your original source audio is never touched
- **Hide/Show charts** toggles the type distribution bar chart and donut pie chart
- The dashboard stays visible above the table — collapse it to maximize table space

### Scan from the Web UI

Click **Scan from...** in the header to run a new scan without leaving the browser:

1. **Source** — browse to the folder of samples you want to index (server-side folder browser; the browser's native file picker can't expose absolute filesystem paths, so this walks the filesystem via a backend API instead)
2. **Mode** — `catalog-only` (index without copying) or `organize` (also copy samples into `Key/`/`Unsorted/` folders)
3. **Destination** — where the index and (optionally) organized folders are written
4. **Options** — library ID/name, dry run, and **Workers**. Default is 1 worker, which is the safest option: each file is analyzed individually so a crash never loses more than the current file. Raise it for speed once you know the library scans cleanly
5. **Progress** — live phase (discovering/analyzing/indexing/saving), file count, elapsed time, and collapsible log output
6. **Done** — the new library's card appears on the dashboard automatically, no page refresh needed

Known scan locations are remembered (`~/.sample-key-indexer/scan_history.json`) and auto-loaded the next time you start `sample-key-indexer-web`, even if you only pass one index path on the command line.

### Sketches — Analyze Ideas Without Audio

Made a bass loop on your MPC and want the same key/mood/compatibility analysis your scanned samples get — without recording it? Click **✏ New Sketch** in the header. The sketch editor opens as a full page with three steps:

1. **Details** — name, key (MPC-style flat/sharp labels like "D# / Eb"), minor/major, BPM, bars, beats/bar, type (Bass, Leads, Pads, …), and optional frequency register (sub/low/mid/high)
2. **Notes** *(optional)* — a piano-roll grid modeled on the MPC's Grid View:
   - **Pencil / Eraser / Select** tools with MPC interactions: click to add, drag to move, drag the right edge to resize, double-click to erase, shift-click to multi-select
   - **Rows filtered to your scale** like Pad Perform, root notes highlighted red like root pads; a Chromatic toggle shows all 12 notes
   - **T.C. divisions** labeled in step terms — `1/8 · 8 steps/bar` through `1/64 · 64 steps/bar` including triplets — with Absolute/Relative/Off snap. Step gridlines redraw to match the selected division
   - **Velocity lane** with a slider per note; Transpose ±1, Duplicate, octave shift, Clear
3. **Analysis** — the same engine that powers scanned samples: key confirmation, mood, out-of-scale note warnings, all five compatible keys with diatonic chords, progressions to try with roman numerals, transition suggestions — plus **⬇ Download your notes as MIDI**, ready to load straight back onto the MPC as a pattern

**Save Sketch** stores it in `~/.sample-key-indexer/sketches.sqlite`, and it appears on the dashboard as a special **✏ Sketch** card (dashed border, no misleading "missing" warnings — sketches have no audio by design). Saved sketches auto-load on startup like any library. In the Browse table, sketch rows show a **✏ Sketch** status badge with inline **⬇ MIDI** download and **✕ delete** actions.

### Browse Tab

After loading a library, the **Browse** tab shows all samples in a sortable, paginated table.

- **Filter bar** — search by name/key/path/type, filter by playback status, category, type, key, source, brightness, warmth, BPM range, confidence threshold, or unsorted-only
- **Sort** — click any column header to sort ascending/descending
- **Pagination** — top and bottom bars with rows-per-page selector (100, 250, 500, 1000), Previous/Next buttons, and page indicator
- **Click a row** to open the sample detail panel

### Sample Detail Panel

A slide-over panel from the right showing everything about a sample:

- **Review diagnostics** (if flagged) — collapsible section at the top showing why the sample was flagged, engine comparison table, assessment, and CLI commands to investigate. "Jump to details" links scroll to relevant sections with a highlight
- **Audio player** — WaveSurfer.js waveform with play/pause/stop (when audio is available)
- **Metadata grid** — key, root, notes, chords, BPM, confidence, duration, format, sample rate, category, type, timbre, loudness, frequency features
- **Frequency chart** — horizontal bar chart of fundamental, centroid, bandwidth, rolloff
- **MFCC chart** — timbre shape with positive/negative coefficient bars
- **Piano keyboard** — chromatic keyboard highlighting the root note and detected notes
- **Deep analysis** — deep key, BPM, tuning, route, engines, chords, note events
- **Musical record** — combined key/tonic/scale/BPM/confidence from all engines
- **Compatible keys** — same key, relative, dominant, subdominant, parallel with diatonic chords
- **Progressions** — chord progressions to try with mood labels and MIDI download buttons
- **Mood & transitions** — primary mood, supporting moods, suggested transitions
- **Mark reviewed** — button to mark the sample as reviewed (updates SQLite index)

### Review Tab

The **Review** tab shows samples flagged by the analysis engines for manual inspection.

- **Summary stats** — flagged count, percentage of library, reviewed count, remaining, lowest confidence
- **Filter by reason** — click reason badges (e.g., `engine_key_disagreement`, `filename_bpm_anchor`) to filter the queue. Click again to clear
- **Filter by type** — click type badges to see only flagged samples of that type
- **Include reviewed** — toggle to show/hide already-reviewed samples
- **Paginated list** — each row shows confidence (color-coded), sample name, review reason badges, type, and key
- **Click a row** to open the detail panel with diagnostics

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑` / `↓` | Highlight previous/next row in the table |
| `Enter` | Open the detail panel for the highlighted row |
| `Escape` | Close the detail panel |
| `Tab` | Cycle through focusable elements within the detail panel (trapped when open) |

### Theme Switcher

The header has a segmented control with four themes: **Studio** (warm teal), **Indigo** (cool purple), **Paper** (terracotta), and **Dark** (warm charcoal). All colors swap instantly via CSS variables — no page reload needed. Your choice is saved to localStorage.

### Project Key & Fit Column

Set the **Project Key** dropdown in the filter bar to the key of the track you're working on. A **Fit** column appears in the table showing:

- **Same key** — exact match
- **Compatible** — relative, dominant, subdominant, or parallel key (will mix cleanly)
- **Out of key** — different key, may clash
- **No key** — sample has no detected key

### Key-Color System

Every key has a unique color derived from its position on the **circle of fifths** (C = 0°, G = 30°, D = 60°, etc.). This color appears everywhere:
- Key chips in the table
- Circle of Fifths wheel in the detail panel
- Piano keyboard highlighting
- Compatible keys dots
- Keys in Your Library chart on the dashboard

Harmonically related keys have similar hues — you can visually scan the table and spot which samples share a key family.

### Circle of Fifths

The detail panel shows an interactive circle of fifths wheel:
- **Solid colored wedge** = detected key
- **Lighter wedges** = compatible keys
- **Grey wedges** = unrelated keys

Click the **?** icon for a legend with the actual colors from the current sample.

---

## Workflows

### Typical First-Time Library Setup

```bash
# 1. Clean up the source library
sample-key-indexer-sanitize /Volumes/USB_01/Samples --dry-run
sample-key-indexer-sanitize /Volumes/USB_01/Samples

# 2. Index and organize (catalog-only if you don't want to copy files)
sample-key-indexer-kitchen-sink /Volumes/USB_01/Samples /path/to/Indexes/usb_01 \
  --keyfinder-convert-retry --keyfinder-workers 8 \
  --deep-analysis smart --deep-analysis-scope musical \
  -- --catalog-only --library-id usb_01 --library-name "USB 01"

# 3. Browse
sample-key-indexer-web /path/to/Indexes/usb_01/metadata_index.sqlite \
  --library-root usb_01=/Volumes/USB_01/Samples
```

### Resuming After a Crash

The index is resumable by default. Just rerun the same command — files with matching path, size, and modification time are skipped. Use `--force` to reprocess everything.

### Browsing Multiple Libraries

```bash
sample-key-indexer-web /path/to/Indexes   # auto-discovers all indexes in subdirectories
```

### Re-enriching an Existing Index

```bash
# Update metadata schema without recopying files
sample-key-indexer /path/to/Samples /path/to/Output --force --dry-run
```

---

## Developing the Frontend

The React frontend lives in `web/` and is completely independent from the Python backend — it communicates via the REST API.

### Tech Stack

| Library | Purpose |
|---------|---------|
| React 19 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool and dev server |
| Tailwind CSS 4 | Utility-first styling |
| TanStack Query | Server state, caching, background refetch |
| Zustand | Client state (filters, pagination, UI) |
| Recharts | Charts (donut, bar, frequency, MFCC) |
| WaveSurfer.js | Audio waveform visualization |

### Setup

```bash
cd web
npm install
npm run dev        # Dev server on :5173, proxies /api to :8765
npm run build      # Production build to web/dist/
npm run type-check # TypeScript checking (no emit)
```

### Testing

The frontend has two test layers — unit tests (no browser or backend needed) and end-to-end tests (Playwright, API mocked via route interception).

```bash
cd web
npm test                 # Unit tests (Vitest + React Testing Library)
npm run test:watch       # Watch mode for TDD
npm run test:coverage    # Coverage report → web/coverage/
npm run test:e2e         # E2E tests (starts Vite dev server automatically)
npm run test:e2e:ui      # Interactive Playwright UI
```

**Unit tests** (`src/**/*.test.{ts,tsx}`):

| File | What's covered |
|------|---------------|
| `src/hooks/useReviewFiltering.test.ts` | Filtering, sorting, pagination, reason counts, page-reset on filter change |
| `src/api/client.test.ts` | All API fetch wrappers, error handling on non-2xx, query param construction |
| `src/store/useAppStore.test.ts` | `applyFilters` (all 11 filter dimensions), `sortSamples` (string/numeric/null ordering) |
| `src/components/Dashboard.test.tsx` | Library card rendering, active highlight, delete confirm/cancel flow, chart toggle |

MSW intercepts every `fetch` call in jsdom so unit tests never hit a real server.

**E2E tests** (`e2e/*.spec.ts`):

| File | What's covered |
|------|---------------|
| `e2e/catalog.spec.ts` | Library cards load, counts, stats section, hide/show charts |
| `e2e/filters.spec.ts` | Search filter, clearing restores all samples |
| `e2e/delete-library.spec.ts` | Delete button visible, cancel leaves card, confirm calls `/api/scan/delete` + `/api/reload` |
| `e2e/scan-wizard.spec.ts` | Wizard opens, folder browser renders, cancel closes |

All API calls are intercepted via Playwright's `page.route()` in `e2e/fixtures.ts` — no Python backend required to run e2e tests.

### CI / GitHub Actions

The workflow at [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs automatically on every pull request to `dev` or `main`, and on every push to `dev`. All three jobs must pass before a PR can be merged.

| Job | Runs on | What it checks |
|-----|---------|---------------|
| **Backend** (Python 3.11 + 3.12) | Ubuntu | `pytest tests/` — pure-logic tests; excludes `test_audio_analysis.py` which needs native audio libs not available on CI runners |
| **Frontend unit** | Ubuntu | TypeScript type-check (`tsc`) + Vitest unit tests |
| **E2E** | Ubuntu | Playwright/Chromium suite — only starts after unit tests pass |

If a Playwright run fails in CI, the full `playwright-report/` (including failure screenshots) is uploaded as a GitHub Actions artifact with a 7-day retention window — visible in the **Actions** tab of the PR.

To run the exact same checks locally before pushing:

```bash
# Backend
pytest tests/ --ignore=tests/test_audio_analysis.py

# Frontend unit + type-check
cd web && npm run type-check && npm test

# E2E
cd web && npm run test:e2e
```

### Project Structure

```
web/
├── src/
│   ├── main.tsx                  # React root, QueryClient, theme boot
│   ├── App.tsx                   # Layout, routing, library loading, theme switcher
│   ├── api/
│   │   └── client.ts             # Typed fetch wrappers for all API endpoints
│   ├── store/
│   │   └── useAppStore.ts        # Zustand store (filters, sort, pagination, theme, project key)
│   ├── hooks/
│   │   └── useReviewFiltering.ts # Review tab filter/stats logic
│   ├── lib/
│   │   ├── key-color.ts          # Circle-of-fifths pitch-class color system
│   │   └── key-compat.ts         # Key compatibility (relative, dominant, parallel)
│   ├── utils/
│   │   ├── filters.ts            # uniqueValues helper
│   │   └── sample.ts             # getSampleField accessor
│   ├── styles/
│   │   ├── tokens.css            # Design tokens (4 themes via CSS variables)
│   │   └── theme.css             # Tailwind @theme mapping
│   ├── types/
│   │   └── api.ts                # TypeScript interfaces for all API responses
│   └── components/
│       ├── detail/               # Detail panel sub-components
│       │   ├── PanelShell.tsx    # Modal logic, animations, focus trap
│       │   ├── PanelHeader.tsx   # Review button, close, reason badges
│       │   ├── MetadataGrid.tsx  # Sample metadata chip grid
│       │   ├── PianoKeyboard.tsx # Chromatic keyboard with key-colors
│       │   ├── DeepAnalysisSection.tsx
│       │   └── MusicalContext.tsx # Compatible keys, progressions, mood
│       ├── ui/                   # Shared UI primitives
│       │   ├── Chip.tsx          # Label/value pair
│       │   ├── ChipGrid.tsx      # Grid of chip cards
│       │   ├── SectionLabel.tsx  # Section headers
│       │   ├── ErrorBoundary.tsx # Render error catch + retry
│       │   └── InfoTooltip.tsx   # Portal tooltip with color dots
│       ├── AudioPlayer.tsx       # WaveSurfer.js waveform + controls
│       ├── CircleOfFifths.tsx    # SVG circle-of-fifths wheel
│       ├── Dashboard.tsx         # Library cards + type/key charts
│       ├── FilterBar.tsx         # Filter bar with project key selector
│       ├── FrequencyChart.tsx    # Horizontal bar chart (Recharts)
│       ├── KeyDistribution.tsx   # Keys in Your Library chart
│       ├── MFCCChart.tsx         # Timbre coefficient chart (Recharts)
│       ├── PaginationBar.tsx     # Shared pagination (top + bottom)
│       ├── ReviewDiagnostic.tsx  # Engine comparison + CLI commands
│       ├── ReviewTab.tsx         # Flagged samples queue with filters
│       ├── SampleDetailPanel.tsx # Slide-over panel orchestrator
│       ├── SampleTable.tsx       # Table with key chips, confidence bars, fit column
│       └── TypePieChart.tsx      # Donut chart (Recharts)
├── index.html
├── e2e/                              # Playwright e2e tests
│   ├── fixtures.ts                   # Shared API mock (page.route intercepts)
│   ├── catalog.spec.ts
│   ├── filters.spec.ts
│   ├── delete-library.spec.ts
│   └── scan-wizard.spec.ts
├── src/
│   └── ...
│   ├── hooks/
│   │   └── useReviewFiltering.test.ts
│   ├── api/
│   │   └── client.test.ts
│   ├── store/
│   │   └── useAppStore.test.ts
│   ├── components/
│   │   └── Dashboard.test.tsx
│   └── test/
│       ├── setup.ts                  # jest-dom matchers + MSW server lifecycle
│       └── mocks/
│           ├── handlers.ts           # MSW request handlers + shared fixture data
│           └── server.ts             # MSW node server setup
├── vite.config.ts                    # Vitest config embedded under `test:` key
├── playwright.config.ts
├── tsconfig.json
├── tsconfig.app.json
└── tsconfig.e2e.json
```

### How It Works

- **Backend** (`sample_key_indexer/web_app.py`) serves the API and static files. In production, it serves the built React app from `web/dist/`. In development, Vite runs on `:5173` and proxies `/api/*` to the Python server on `:8765`.
- **State** is split: server state (catalog, samples, sample details) is managed by TanStack Query with caching; client state (filters, sort, pagination, theme, project key) lives in Zustand.
- **Theming** uses CSS custom properties via `data-theme` attribute — all color utilities (`bg-surface`, `text-ink`, `border-line`) resolve through `var()` and swap instantly when the theme changes. No `dark:` variants needed.
- **Key-color system** (`lib/key-color.ts`) maps each musical key to a unique hue based on the circle of fifths. Used everywhere keys appear (table chips, piano, wheel, charts).
- **Samples are loaded in chunks** — 15,000 per request — and cached per library. Switching libraries loads from cache if already fetched.
- **Table rows are memoized** — only changed rows re-render when selection or highlight changes.
- **Detail panel** fetches full sample data on demand via `/api/sample?id=N`, which includes musical context (compatible keys, progressions, mood) computed server-side.
- **Preferences** (theme, page size, project key) are persisted to localStorage across sessions.

---

## Troubleshooting

### I pulled new code but the new feature isn't in the UI

You're almost certainly viewing a stale frontend build. The backend at `:8765` serves the last `npm run build` output from `web/dist/` — it never rebuilds automatically. Fix:

```bash
cd web && npm run build
```

Then restart `sample-key-indexer-web` and hard-refresh the browser (Cmd+Shift+R). Alternatively run in [development mode](#option-b--development-mode-live-reload-two-servers) at `http://localhost:5173`, which always shows the latest code.

### All samples have `root_note: null`, `key: null`, `type: FX`

The audio backend didn't load. Common cause on macOS with pyenv: missing XZ/LZMA support.

```bash
brew install xz
pyenv uninstall 3.11.9 && pyenv install 3.11.9
rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate
pip install -e .
sample-key-indexer /any/path /any/output --doctor
```

After fixing, delete the bad index or rerun with `--force`.

### Worker crashes / segfault on every file (`Worker crashes: N files`)

If analysis crashes on nearly every file (visible as repeated `Warning: worker crashed while analyzing ...` lines), this is usually a `numba`/`numpy` version mismatch causing a native segfault inside `librosa.yin()`, not a code bug. Pin known-compatible versions:

```bash
pip install 'numpy<2.0' 'numba==0.60.0' 'llvmlite==0.43.0'
```

Then rerun your scan — the batch-resilient indexer (added in V5) will skip and retry any file that still crashes in isolation, so a handful of stubborn files won't block the rest of the library.

### KeyFinder not found

Ensure `keyfinder-cli` or `keyfinder` is on your PATH. Check with:

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite --backend-check
```

### Module not installed

If the console script isn't available, run as a module:

```bash
python -m sample_key_indexer.cli --help
python -m sample_key_indexer.web_app /path/to/metadata_index.sqlite
python -m sample_key_indexer.review_report /path/to/metadata_index.sqlite
```

---

## Version History

### V5 (Current) — React Frontend
- **Sketches**: describe a musical idea (key, BPM, bars, type) and optionally enter the notes you played on an MPC-style piano-roll grid (Pad Perform scale filtering, T.C. divisions 1/4–1/64 with triplets, Absolute/Relative/Off snap, velocity lane, transpose/duplicate) — then get the full key/mood/compatible-keys/progressions/transitions analysis without any audio file, download your notes as MIDI, and save sketches as a persistent ✏ dashboard library with per-sketch MIDI download and delete
- **Scan from Web UI**: in-browser scan wizard (server-side folder browser, catalog-only/organize mode, configurable workers, live progress), delete-library action on dashboard cards (removes index files, organized folders, and in-memory server state together), known scan locations auto-load on backend startup from scan history
- **Crash-resilient batch analysis**: core indexer processes files in batches of 50 instead of one giant worker pool — a crashing file only loses its own batch (retried in isolated mode) instead of the entire run
- **Phase 1**: Vite + React 19 + TypeScript scaffold with Tailwind CSS, TanStack Query, typed API client
- **Phase 2**: Zustand store, 13-dimension filter bar, sortable paginated sample table, collapsible dashboard with library cards
- **Phase 3**: Sample detail slide-over panel with WaveSurfer.js audio player, metadata grid, piano keyboard, compatible keys, chord progressions with MIDI download, mood & transitions
- **Phase 4**: Recharts visualizations (donut pie chart, frequency features, MFCC timbre), Review tab with paginated queue, clickable reason/type filter badges, review diagnostics with engine comparison table and CLI commands, Mark Reviewed action
- **Phase 5**: Dark mode with system preference detection, keyboard navigation (arrow keys, Enter, Escape), focus trap in detail panel, filter bar scoped to Browse tab only
- **Refactoring**: SampleDetailPanel split (621→129 lines), shared UI components (Chip, ChipGrid, SectionLabel, ErrorBoundary), useReviewFiltering hook, debounced search, AudioPlayer error handling
- **Phase A**: Circle of fifths SVG wheel, key-color system (oklch hues from circle of fifths), Keys in Your Library distribution chart, key-colored chips and confidence meter bars in table, design tokens with 4 themes (studio/indigo/paper/dark), theme switcher, Google Fonts, InfoTooltip portal
- **Phase B**: Project key selector with Fit column (Same key/Compatible/Out of key/No key), key compatibility logic (relative, dominant, subdominant, parallel), persistent preferences (theme, page size, project key) in localStorage
- **Phase C**: Documentation update, QA across all themes
- **Testing**: Vitest + React Testing Library unit tests (48 tests across hooks, API client, store, and components); Playwright e2e suite (catalog, filters, delete flow, scan wizard) with full API mocking via MSW and `page.route()` — no backend required to run either suite
- **CI**: GitHub Actions workflow (`.github/workflows/ci.yml`) runs backend pytest (Python 3.11 + 3.12), frontend unit tests, and Playwright e2e on every PR to `dev` or `main` — PRs are blocked until all jobs pass

### V4
- Routed deep-analysis backends (Essentia tonal/tuning, loop BPM/ticks, monophonic note events, Basic Pitch polyphonic transcription)
- Deep analysis is resumable — skips samples with up-to-date results
- LAN hardening for web UI (IP/CIDR allowlists, auth tokens)
- Sanitize tuning improvements
- Kitchen-sink summary and deep analysis integration

### V3.7
- Multi-library web browser with per-library stats and playback filters

### V3.6
- KeyFinder as stored comparison backend
- Classification quality improvements (filename weighting, loop/drum detection)
- Backend availability checks
- Classification audits

### V3.5
- Deep-review failure reporting and triage (JSON/CSV export)

### V3.4
- Deep-review failure management (skip known crashes, `--retry-deep-failed`)

### V3.3
- Deep review mode (plan, rerun, crash isolation, fallback retry)

### V3.2
- `ffprobe` duration probing with fallbacks

### V3.1
- Warning capture, ultra-short/silent audio handling, improved run reports

For detailed per-version notes, see [CHANGELOG.md](CHANGELOG.md).

For the full command reference, see [docs/COMMAND_CHEATSHEET.md](docs/COMMAND_CHEATSHEET.md). For project context and architecture, see [docs/PROJECT_MEMORY.md](docs/PROJECT_MEMORY.md).
