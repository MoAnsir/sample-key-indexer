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
- [Commands](#commands)
  - [sample-key-indexer](#sample-key-indexer--core-indexer)
  - [sample-key-indexer-kitchen-sink](#sample-key-indexer-kitchen-sink--all-in-one)
  - [sample-key-indexer-review](#sample-key-indexer-review--enrichment--verification)
  - [sample-key-indexer-web](#sample-key-indexer-web--web-browser-ui)
  - [sample-key-indexer-sanitize](#sample-key-indexer-sanitize--library-cleanup)
- [Output Structure](#output-structure)
- [Analysis Engines](#analysis-engines)
- [Workflows](#workflows)
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

### 5. Full pipeline in one command

```bash
sample-key-indexer-kitchen-sink ~/Music/MySamples ~/SampleIndexes/my_library \
  --keyfinder-convert-retry --keyfinder-workers 8 \
  --deep-analysis smart --deep-analysis-scope musical
```

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
| `--workers N` | auto (1–4) | Number of parallel analysis workers |
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

## Troubleshooting

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

### V4 (Current)
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
