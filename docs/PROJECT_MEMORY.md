# Project Memory

This file is the long-lived project context for humans and AI agents. Read it before making changes so the codebase keeps its intent across branches, sessions, and future work.

## Purpose

`sample-key-indexer` scans large sample libraries, estimates musical key/root/BPM and useful audio features, classifies samples, writes searchable metadata, and optionally copies or moves audio into an organised `Key/` and `Unsorted/` tree.

The user workflow is based around multiple removable drives. Each USB or SD card should be indexed as a separate library so the web app can search metadata even when the drive is not mounted. Audio playback should become available again when the matching source or organised drive is mounted and passed to the web app.

The short one-page daily command guide lives in `docs/DAILY_COMMANDS.md`. The fuller command reference lives in `docs/COMMAND_CHEATSHEET.md`. Keep both updated when a feature adds or changes a command the user is likely to reuse. The daily guide should include both catalog-only indexing and organising/copying into `Key/` and `Unsorted/` for moving onto USB/SD devices.

## Current Branch State

- `dev` is the local integration branch.
- `dev` includes completed V3.7 multi-library browser work.
- No V3.8 branch has been created yet.
- There is currently no configured git remote in this checkout, so "push to dev" means commit locally on the `dev` branch unless a remote is added later.
- Recent completed local dev commits:
  - `357a89b Start V3.1 bulk run quality`
  - `2b22882 Start V3.2 ffprobe duration probing`
  - `602e884 Add deep review rerun diagnostics`
  - `c374164 Start V3.4 deep review failure tracking`
  - `18009fb Complete V3.5 failure triage reporting`
  - `d6eef47 Add V3.6 KeyFinder review policy`
  - `f40173a Start V3.7 multi-library browser UX`
  - `794a4b1 Document V3.7 multi-library verification`

## Core Commands

Install in editable mode:

```bash
cd /Users/mohammedansir/DEV/Projects/sample-key-indexer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run a catalog-only index for a removable library:

```bash
caffeinate -dimsu sample-key-indexer \
  /path/to/source_samples \
  /path/to/SampleIndexes/library_id \
  --catalog-only \
  --library-id library_id \
  --library-name "Human Library Name" \
  --analysis-profile balanced \
  --engines librosa,essentia \
  --workers 4 \
  --write-every 25
```

Run the browser from original source paths:

```bash
sample-key-indexer-web \
  /path/to/SampleIndexes/library_id/metadata_index.sqlite \
  --library-root library_id=/Volumes/USB/source_samples
```

Run the browser from an organised `Key/` and `Unsorted/` tree:

```bash
sample-key-indexer-web \
  /path/to/SampleIndexes/library_id/metadata_index.sqlite \
  --destination-root library_id=/Volumes/USB/SAMPLEZ
```

Use quotes around paths with spaces:

```bash
sample-key-indexer-web \
  /path/to/metadata_index.sqlite \
  --destination-root "usb_01=/Volumes/SSK Drive/SAMPLEZ"
```

## Packages And Tools

Required Python packages:

- `essentia`: harmonic/key analysis backend used by the normal balanced/deep workflows.
- `librosa`: baseline audio loading, chroma, tempo, and feature analysis.
- `numpy`: numeric/audio arrays.
- `soundfile`: fast WAV/AIFF metadata and loading support.
- `tqdm`: progress bars.

Required external tools:

- `keyfinder-cli` or `keyfinder`: required external key-comparison backend. Python packaging cannot install this binary, so it must be installed separately and available on `PATH`.

Optional external tools and future options:

- `ffprobe`: V3.2 uses it first, when available, for duration probing and long-file skip decisions.
- Sonic Annotator with QM Vamp Plugins: possible later deep harmonic analysis backend if KeyFinder comparison is not enough.
- `aubio`: possible small-footprint onset/tempo utility, only if better onset/tempo becomes useful without adding a large dependency.

## Major Features

### Discovery And Supported Files

Discovery lives in `sample_key_indexer/discovery.py`. Supported audio extensions are currently discovered from the supported extension set. Unsupported files are counted and reported by extension and total size at the end of a run.

Long files are skipped by default using `--max-duration 60`. Use `--include-long-files` to disable duration skipping. V3.2 duration probing uses:

1. `ffprobe` in `auto` mode when installed.
2. `soundfile` fallback.
3. `librosa` fallback.

The CLI option is:

```bash
--probe-backend auto|ffprobe|python
```

### Analysis

Analysis lives in `sample_key_indexer/audio_analysis.py`.

The baseline engine is librosa. The balanced and deep profiles include `essentia` in the selected engine list. Essentia is a required Python dependency because the normal user workflow runs `--engines librosa,essentia`.

Important analysis behavior:

- Python warnings are captured into `analysis.warnings` instead of flooding the terminal.
- Very short or near-silent audio gets a lightweight result with review flags rather than full harmonic analysis.
- Final key/root decisions come from a consensus layer that compares librosa, Essentia, and filename key hints.
- Review reasons are stored in metadata for later filtering and reruns.

### Classification And Routing

Classification lives in `sample_key_indexer/classify.py`.

Classification uses filename evidence, nearby folder evidence, and audio features. Filename tokens are weighted higher than folder tokens because real sample packs often contain misleading folders after earlier sorting, while the filename usually carries the strongest clues: drum/fill/beat/hat/kick/snare, BPM, section, key, pack, artist, and index. Loop-like filename tokens such as `fill`, `beat`, `bpm`, `loop`, `ptn`, and `riff` can force even short files into `Loops` instead of `OneShots`.

The CLI skips supported audio whose filename indicates a full arrangement/demo mix via `fullmix` or `full mix`. These files are usually full songs rather than reusable samples. They are reported as `Not copied - ignored filename patterns` and can be included deliberately with `--include-ignored-files`.

Routing lives in `sample_key_indexer/routing.py`. Samples with usable key/root are routed under `Key/<key>/...`. Samples with no usable root/key go under `Unsorted/...`.

Use `--catalog-only` for removable-drive workflows when the goal is metadata only and no audio copying. Use normal runs when building an organised output tree.

### Metadata Storage

Metadata storage lives in `sample_key_indexer/index_store.py`.

The SQLite index is the working source of truth:

```text
metadata_index.sqlite
```

JSON is exported for compatibility and inspection:

```text
metadata_index.json
```

The index is resumable. Existing records are skipped when path, size, and modified time match unless `--force` is passed.

Metadata records include:

- `file`: path, relative path, name, format, duration, sample rate, size, modified time.
- `library`: removable-library ID, display name, and original root.
- `musical`: root, key, scale confidence, notes, chords, BPM.
- `audio_features`: loudness, frequency, timbre, MFCC.
- `classification`: category, type, subtype, source, confidence.
- `analysis`: engine details, warnings, raw program decisions, final decision, review flags.
- `routing`: destination path and routing errors.

### Web App

The web app lives in `sample_key_indexer/web_app.py` and `sample_key_indexer/web_static/`.

It can read one or more JSON or SQLite indexes. The UI remains useful without mounted audio because metadata is stored locally. Playback status is recomputed on each API load so plugging in a USB and refreshing the page can make files playable.

Playback path resolution order:

1. Existing `routing.destination`.
2. `--destination-root LIBRARY_ID=/mounted/organised/root` plus the stored `Key/` or `Unsorted/` relative path.
3. Existing original `file.path`.
4. `--library-root LIBRARY_ID=/mounted/source/root` plus stored `file.relative_path`.

The browser may cancel audio range requests when users click around. Broken pipe and connection reset errors during audio streaming should be treated as normal browser behavior.

### Review Reports

`sample_key_indexer/review_report.py` summarizes samples that need review. It currently counts review reasons/types and prints low-confidence examples.

V3.3 adds deep review mode to the review command. It selects records with low confidence, `needs_review`, key/root disagreements, analysis warnings, or analysis errors. Drum, percussion, and FX records are not selected just for weak key confidence because harmonic reruns usually cannot improve them; they need warnings or errors to enter the queue. This filter checks stored type labels and obvious path/name tokens, which keeps misclassified percussion folders such as Dholak/Khanjira/Idakka/Udakai out of harmonic review unless they also have warnings or errors. V3.3 can print a plan, dry-run the rerun counts, or re-analyze only selected records and upsert them into the same metadata index. Real reruns isolate each selected file in a worker process. If deep/balanced analysis crashes, the file is retried once with the safer `fast`/`librosa` path before being counted as a failed worker crash. `--report-json` writes a rerun report with counts plus examples for missing audio, analysis errors, worker crash failures, and fallback successes.

Plan command:

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite --deep-plan --limit 100
```

Rerun command:

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --deep-rerun \
  --library-root library_id=/Volumes/USB/source_samples \
  --limit 500 \
  --report-json /path/to/deep_review_report.json
```

Use `--destination-root` instead of `--library-root` when the mounted audio lives in an organised `Key/` and `Unsorted/` tree. Deep reruns preserve the existing library ID, relative path, library root, and routing destination so catalogs remain stable.

V3.4 starts deep-review failure management. Files that crash both the primary deep rerun and the `fast`/`librosa` fallback are marked in `analysis.deep_review` with `failed`, `reason`, `attempts`, `last_attempt_at`, `profile`, `engines`, and `path`. Deep plans skip those known failures by default so a library does not keep getting stuck at the same crashy files. Use `--retry-deep-failed` when intentionally retesting after changing engines, dependencies, or analysis settings.

## V3 Roadmap

Completed:

- V3.1 Bulk Run Quality
  - Capture Python library warnings into metadata.
  - Tiny/near-silent fast path.
  - Final analysis report with error/review/confidence/disagreement/warning counts.
- V3.2 File Probing
  - Optional `ffprobe`-first duration probing.
  - `--probe-backend` switch.
  - Duration probe report.
- V3.3 Deep Review Mode
  - `--deep-plan` selects low-confidence, needs-review, disagreement, warning, and error records.
  - `--deep-rerun` reprocesses selected candidates instead of reprocessing the whole library.
  - Non-harmonic drum/percussion/FX records are ignored unless they have warnings or errors.
  - Reruns preserve SQLite metadata identity, library path metadata, and routing destinations.
  - `--dry-run`, `--limit`, and `--low-confidence` keep reruns controlled.
  - Current before/after summary counts selected, processed, missing audio, improved confidence, still-needs-review, errors, worker crashes, and fallback successes.
  - `--report-json` stores rerun diagnostics for missing files, analysis errors, crash failures, and fallback successes.
- V3.4 Deep Review Failure Management
  - Persist double-crash failures into `analysis.deep_review`.
  - Skip known deep-review failures by default.
  - `--retry-deep-failed` includes previously failed records for deliberate retesting.
- V3.5 Failure Reporting and Backend Triage
  - `--deep-failures` reports files marked `analysis.deep_review.failed`.
  - `--failures-json` and `--failures-csv` export the failure report.
  - Summarize failures by reason, library, format, type, duration bucket, and path family.
  - Add lightweight triage hints when failures share a pattern, such as short WAV files crashing the deep librosa+essentia path.

Active:

- V3.6 Classification Quality
  - Improve sample type/category routing by combining filename tokens, folder context, and audio features.
  - Filename evidence should beat conflicting folder evidence, for example `HH_Open_01.wav` inside a `Kicks` folder should classify as `Hat`.
  - Drum loop indicators such as `drum`, `beat`, `fill`, `roll`, and `bpm` should keep drum material out of misleading `MelodyLoops`, `Leads`, and `FXLoops` buckets.
  - Full arrangement files named `fullmix` or `full mix` are ignored by default so they are not copied into organised sample folders.
  - `--classification-audit` scans an existing index for suspicious category/type decisions before rebuilding an organised physical device.
  - Keep key analysis and KeyFinder comparison unchanged while improving type routing.

- V3.6 Deep Backend Experiments
  - `--backend-check` prints local availability for required KeyFinder CLI plus optional Sonic Annotator, QM Vamp Plugins, and aubio.
  - The backend check also summarizes recorded deep-review failures so backend experiments stay focused on real crash patterns.
  - `--keyfinder-experiment` runs KeyFinder CLI against recorded deep-review failures, reports successes/errors and stored key/root matches, and can write `--keyfinder-json`.
  - `--keyfinder-enrich` stores KeyFinder output under `analysis.external.keyfinder` without changing `musical.key`, `musical.root`, `analysis.final_decision`, routing, or copied files.
  - `--keyfinder-compare` prints a read-only report over stored `analysis.external.keyfinder`, grouped by library, sample type, confidence bucket, status, and match/disagreement decision.
  - `--keyfinder-apply-review` applies the V3.6 review-only policy: add `keyfinder_high_confidence_disagreement` to review reasons when a successful KeyFinder result strongly disagrees with a high-confidence stored key/root. It does not change final key/root/confidence/routing.
  - `--keyfinder-scope failures|review|all` controls whether KeyFinder runs against known deep failures, review candidates, or every sample in the selected index.
  - `--keyfinder-convert-retry` retries KeyFinder failures via temporary ffmpeg conversion to 16-bit PCM WAV.
  - KeyFinder is now the required stored comparison/review signal, not the main key decision.
  - Daily and full cheat-sheet "kitchen sink" workflows are two-step: run `sample-key-indexer` to analyze/organize, then run `sample-key-indexer-review --keyfinder-enrich --keyfinder-scope all --keyfinder-convert-retry` against the finished SQLite index.

Parked until more devices are available:

- Run `--keyfinder-enrich --keyfinder-scope all --keyfinder-convert-retry` on at least one more real library so KeyFinder agreement/disagreement can be compared beyond SD 02 Trad.
- Run the comparison report against at least one more real library after enrichment so match/disagreement behavior can be compared across libraries.
- Keep the main key decision unchanged during V3.6 and revisit cross-library KeyFinder scoring after more physical devices have been indexed.

Likely next phases:

- V3.7 Multi-Library UX Polish
  - Improve web-app/library filtering and mounted-drive clarity for multiple USB/SD indexes.
  - Make it easy to see which libraries are searchable, playable, missing audio, or using source-vs-organised playback roots.
  - Started on branch `v3.7-multi-library-ux`: web API returns library summaries, each sample now carries `playback_source`, and the browser shows library cards plus Library/Playback filters.
  - Verified with `sd_02_trad_v32_probe` plus `usb_01` loaded together: the browser showed 72,757 total samples across 2 libraries, the USB library became playable when mounted at `/Volumes/SSK Drive/SAMPLEZ`, and playback resolved from the mounted organised USB tree.
- V3.8 Optional Backend Expansion
  - Revisit Sonic Annotator/QM Vamp Plugins only if KeyFinder comparison does not provide enough harmonic evidence.
  - Revisit aubio only for onset/tempo needs, not primary key detection.

Later:

- Optional deep harmonic backend integration with Sonic Annotator/QM Vamp Plugins, if the V3.6 checks prove useful.
- Compare stored `analysis.external.keyfinder` results across more physical devices when they exist. Do not change final key scoring unless a later phase deliberately reopens the V3.6 review-only policy.
- Optional aubio onset/tempo utility if tempo/onset quality needs a small-footprint boost.
- Multi-USB UX polish.

## Known Real-World Workflows

USB 01 catalog run used:

```bash
PYTHONWARNINGS=ignore caffeinate -dimsu sample-key-indexer \
  /Users/mohammedansir/Desktop/Samples_to_detect \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01 \
  --catalog-only \
  --library-id usb_01 \
  --library-name "USB 01 - Samples_to_detect" \
  --analysis-profile balanced \
  --engines librosa,essentia \
  --workers 4 \
  --write-every 25
```

The user's organised USB playback root for USB 01 was:

```text
/Volumes/SSK Drive/SAMPLEZ
```

and it contains:

```text
Key/
Unsorted/
```

Correct browser command for that organised tree:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --destination-root "usb_01=/Volumes/SSK Drive/SAMPLEZ"
```

SD 02 Trad V3.2 verification used:

```bash
caffeinate -dimsu sample-key-indexer \
  /Users/mohammedansir/Desktop/Samples_to_detect/SAMPLES/Big.Fish.Audio.Indian.Traditions.Rex2.Wav \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe \
  --catalog-only \
  --library-id sd_02_trad_v32_probe \
  --library-name "SD 02 Trad V3.2 Probe Test" \
  --analysis-profile balanced \
  --engines librosa,essentia \
  --workers 4 \
  --write-every 25 \
  --probe-backend auto
```

Expected verified V3.2 signal:

```text
Duration probe report:
  ffprobe: 4411 files
  soundfile fallback: 0 files
  librosa fallback: 0 files
  Unknown backend: 0 files
  Failed duration probes: 0 files
```

V3.6 backend check against the SD 02 Trad failure set used:

```bash
.venv/bin/python -B -m sample_key_indexer.review_report \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --backend-check
```

Verified signal on this machine:

```text
Deep-review failure targets: 5 files
Failure path families:
  Indian Melodic / Flute: 2
  Indian Melodic / Mandolin: 2
  Indian Melodic / Sitar: 1
KeyFinder CLI: available (/usr/local/bin/keyfinder-cli) [required]
Sonic Annotator: missing [optional]
aubio: missing [optional]
QM Vamp Plugins: missing
```

The first real V3.6 backend experiment uses KeyFinder CLI against the recorded deep failures before adding Sonic Annotator/QM or aubio integration.

KeyFinder experiment command:

```bash
.venv/bin/python -B -m sample_key_indexer.review_report \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-experiment \
  --keyfinder-json /tmp/v36_keyfinder_experiment.json
```

Verified result:

```text
Selected deep failures: 5 files
Processed: 4 files
Successes: 4 files
Errors: 1 files
Matches stored root: 2 files
FlutePtn080 11.wav: Unable to resample audio into 16bit PCM data
FltBhairavi115 01c.wav: Fm / F_minor, root match true
MndMinLick080 01(lp5).wav: Bm / B_minor, root match false
MndRatiPriya100 13(lp).wav: Bbm / A#_minor, root match true
StrBhairaviAlap 01a.wav: E / E_major, root match false
```

Interpretation: KeyFinder can analyze most of the current crash set and gives useful comparison data, but it should not replace the current key decision yet. Treat it as the required external comparison signal until more libraries confirm whether its output should influence confidence.

Full-index KeyFinder experiment on the same selected folder:

```bash
.venv/bin/python -B -m sample_key_indexer.review_report \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-experiment \
  --keyfinder-scope all \
  --keyfinder-json /tmp/v36_keyfinder_all_sd_02_trad.json
```

Verified result:

```text
Selected samples: 4411 files
Processed: 2452 files
Successes: 2452 files
Errors: 1959 files
Matches stored key: 779 files
Matches stored root: 1020 files
All 1959 errors were: Unable to resample audio into 16bit PCM data
Most errors were in Indian Percussion / WAV: 1447 files
```

Interpretation: KeyFinder is usable at pack scale, but nearly 44% of this pack fails due to its resampling path. It is more useful as a comparison/reporting backend than as the main key engine until a conversion retry path is tested.

V3.6 conversion retry uses ffmpeg, which is installed at `/opt/homebrew/bin/ffmpeg` on this machine. The retry path converts only failed KeyFinder inputs to a temporary 16-bit PCM WAV (`pcm_s16le`), reruns KeyFinder, and removes the temp file when done.

Full-index KeyFinder experiment with conversion retry:

```bash
.venv/bin/python -B -m sample_key_indexer.review_report \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-experiment \
  --keyfinder-scope all \
  --keyfinder-convert-retry \
  --keyfinder-json /tmp/v36_keyfinder_all_sd_02_trad_convert_retry.json
```

Verified result:

```text
Selected samples: 4411 files
Processed: 4411 files
Successes: 4411 files
Conversion attempts: 1959 files
Conversion successes: 1959 files
Conversion errors: 0 files
Errors: 0 files
Matches stored key: 1346 files
Matches stored root: 2041 files
```

Interpretation: ffmpeg conversion fixes the KeyFinder resampling failure completely for this pack. KeyFinder still should not overwrite the main decision yet, but it is now viable as the required comparison backend over full selected indexes.

V3.6 now includes an opt-in metadata enrichment command that stores KeyFinder output under `analysis.external.keyfinder`, including raw key, normalized key, root, stored key/root match flags, conversion status, errors, path, command, scope, and update timestamp. It does not change `musical.key`, `musical.root`, `analysis.final_decision`, routing metadata, or copied files.

Metadata enrichment command:

```bash
.venv/bin/python -B -m sample_key_indexer.review_report \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-enrich \
  --keyfinder-scope all \
  --keyfinder-convert-retry \
  --keyfinder-json /tmp/v36_keyfinder_enrich_all.json
```

Result on SD 02 Trad:

```text
Selected samples: 4411 files
Processed: 4411 files
Successes: 4411 files
Metadata updated: 4411 files
Conversion attempts: 1959 files
Conversion successes: 1959 files
Conversion errors: 0 files
Missing audio: 0 files
Errors: 0 files
Matches stored key: 1346 files
Matches stored root: 2041 files
```

SQLite verification:

```text
total records: 4411
analysis.external.keyfinder.status = success: 4411
analysis.external.keyfinder.conversion_used = true: 1959
```

Interpretation: KeyFinder is ready as the required external comparison signal. V3.6 policy keeps it separate from the main key decision and permits only review-only influence through `--keyfinder-apply-review`.

V3.6 stored comparison report command:

```bash
.venv/bin/python -B -m sample_key_indexer.review_report \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-compare \
  --examples 15 \
  --keyfinder-json /tmp/v36_keyfinder_compare_sd_02_trad.json
```

Result on SD 02 Trad:

```text
Total samples: 4411 files
With KeyFinder metadata: 4411 files
Missing KeyFinder metadata: 0 files
Successes: 4411 files
Errors: 0 files
Conversion used: 1959 files
Matches stored key: 1346 files
Matches stored root: 2041 files
Root-only matches: 695 files
Key/root disagreements: 2370 files
```

Top-level decision counts:

```text
key_and_root_disagree: 2370
key_match: 1346
root_match_key_diff: 695
```

Interpretation: SD 02 is enough to justify a conservative review-only policy, not enough to change final key scoring. Additional device comparisons are parked until more physical libraries are available.

## V3.6 Classification Quality Notes

The USB 01 physical-device test exposed type-routing problems in the organised folders: drum fills under one-shot leads, hi-hats in kick folders, drum loops in melodies, and drum beats/fills in FX. It also showed many `fullmix`/`full mix` files in loop folders; these are full songs and should not be copied by default. The V3.6 classification fix keeps filename and folder evidence separate, scores filename evidence more strongly, treats obvious loop/fill/beat tokens as loop indicators, skips full-mix filename patterns before analysis/copying, and adds `sample-key-indexer-review --classification-audit` so existing indexes can be scanned before re-copying a physical device.

Classification audit command:

```bash
sample-key-indexer-review /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --classification-audit \
  --examples 50 \
  --classification-json /tmp/usb_01_classification_audit.json \
  --classification-csv /tmp/usb_01_classification_audit.csv
```

KeyFinder policy decision: V3.6 does not let KeyFinder replace, boost, or tie-break the final key. It remains external metadata and can optionally add review flags only:

```bash
sample-key-indexer-review /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-apply-review \
  --keyfinder-review-threshold 0.75 \
  --keyfinder-json /tmp/sd_02_keyfinder_review_policy.json
```

V3.6 verification on temporary copies:

- `sd_02_trad_v32_probe`: `--keyfinder-compare` found 4,411 KeyFinder records, 1,346 stored-key matches, 2,041 stored-root matches, 695 root-only matches, and 2,370 key/root disagreements.
- `sd_02_trad_v32_probe`: `--keyfinder-apply-review --dry-run` selected 445 high-confidence disagreements for review-only flags. A non-dry-run on a temp copy updated 445 records and preserved `musical.key` and `analysis.final_decision.key`.
- `sd_02_trad_v32_probe`: `--classification-audit` found 1,845 suspicious classifications.
- `usb_01`: `--keyfinder-compare` found no KeyFinder metadata yet, as expected because USB 01 audio is not currently local.
- `usb_01`: `--keyfinder-apply-review --dry-run` selected 0 records, as expected without KeyFinder metadata.
- `usb_01`: `--classification-audit` found 9,758 suspicious classifications, including 412 `fullmix`/`full mix` files already present in the old index.

## Common Gotchas

- Paths with spaces must be quoted in shell commands.
- If the web app says samples are missing, check whether the correct `--library-root` or `--destination-root` was used.
- Use `--destination-root` for organised `Key/` and `Unsorted/` folders.
- Use `--library-root` for original unorganised source folders.
- The web app can search metadata without the USB mounted, but audio playback requires the source or organised audio files to exist at a resolvable path.
- Native decoder messages from external C libraries may still appear even when Python warnings are captured.
- `BrokenPipeError` during web JSON/static/audio responses usually means the browser cancelled a request or refreshed while loading a large index. It should not be treated as a failed sample.
- `zsh: unknown file attribute: V` is usually shell parsing from unquoted parentheses/globs, not an indexer error.

## Verification Commands

Run before committing feature work:

```bash
.venv/bin/python -B -m unittest discover -s tests
python3 -B -m unittest discover -s tests
PYTHONPYCACHEPREFIX=/tmp/sample-key-indexer-pycache python3 -m py_compile sample_key_indexer/audio_analysis.py sample_key_indexer/cli.py
PYTHONPYCACHEPREFIX=/tmp/sample-key-indexer-pycache python3 -m py_compile sample_key_indexer/review_report.py
git diff --check
```

For web JavaScript changes:

```bash
node --check sample_key_indexer/web_static/app.js
```

## Coding Principles

- Preserve existing metadata compatibility where practical.
- Keep removable-library IDs stable; do not infer identity from mount paths alone.
- Avoid recopying large audio folders unless the user explicitly wants an organised output.
- Prefer catalog-only indexing for removable-drive metadata workflows.
- Keep review/deep analysis incremental so large libraries do not need full reruns.
- Update this memory file whenever a feature changes the workflow, data model, branch plan, or verification process.
