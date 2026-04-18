# Sample Library Key Indexer

A practical V1 local CLI for scanning large sample libraries, estimating root notes and keys, classifying samples, and organising them primarily by musical key.

For durable project context, architecture notes, workflows, branch state, and AI-agent memory, read [`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md). For the short daily one-pager, use [`docs/DAILY_COMMANDS.md`](docs/DAILY_COMMANDS.md). For the full command reference, use [`docs/COMMAND_CHEATSHEET.md`](docs/COMMAND_CHEATSHEET.md).

## Install

```bash
cd /Users/mohammedansir/DEV/Projects/sample-key-indexer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

`librosa` handles the baseline pitch and chroma analysis. `essentia` is installed as a required dependency because the normal balanced workflow uses `--engines librosa,essentia`. `soundfile` is included for WAV/AIFF support; MP3 support depends on the audio backend available to librosa/audioread on your machine.

KeyFinder CLI is also required. It is an external command-line tool, so `pip install -e .` cannot install it from Python packaging metadata. Install it separately and make sure either `keyfinder-cli` or `keyfinder` is on `PATH`; `--doctor` and `--backend-check` fail when it is missing.

## Run

Dry run first:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --dry-run
```

Check the local audio stack without processing files:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --doctor
```

Copy files into the organised library:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised
```

Sanitize a source library in place before scanning. This scans first, prints a removable-file report, then prompts for `quarantine`, `delete`, or `cancel`:

```bash
sample-key-indexer-sanitize /path/to/SampleLibrary
```

Use `--dry-run` to inspect the removable set and write `sanitize_report.json` without changing files:

```bash
sample-key-indexer-sanitize /path/to/SampleLibrary --dry-run
```

Build a searchable catalog without copying audio into `Key/` or `Unsorted`:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/SampleIndexes/USB_01 --catalog-only --library-id usb_01 --library-name "USB 01"
```

Every main indexing run now also writes a machine-readable run log to:

```text
/path/to/output_root/analysis_run_report.json
```

Use `--report-json` to override that location when you want to save the report somewhere else during debugging or comparisons.

V2 uses the balanced analysis profile by default. It keeps the librosa baseline, uses Essentia key analysis, writes a SQLite working index, and exports the JSON metadata used by the browser:

```text
Samples_Organised/metadata_index.sqlite
Samples_Organised/metadata_index.json
```

You can choose a different profile or engine list:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --analysis-profile fast
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --engines librosa,essentia
```

Use the old JSON-only index path if needed:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --no-sqlite
```

By default, files longer than 60 seconds are treated as full songs and skipped. This keeps the library focused on samples and avoids filling the output folder with long tracks. To change the threshold:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --max-duration 90
```

Duration probing uses `ffprobe` when it is installed, then falls back to the Python audio backends. To force one path while testing:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --probe-backend ffprobe
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --probe-backend python
```

The run report JSON includes:

- processed/skipped/unsupported counts
- probe backend counts
- normalized failed-probe reason counts and failed-probe examples
- whether isolated retry mode was triggered after a worker crash
- normalized crash signature buckets with counts and representative example files
- example files for errors, warnings, and review cases
- suspicious-file rollups and explained source/output delta

To include long files anyway:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --include-long-files
```

Move files instead of copying:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --move
```

Run the web browser:

```bash
sample-key-indexer-web /path/to/Samples_Organised/metadata_index.json
```

The browser can also read the V2 SQLite index directly:

```bash
sample-key-indexer-web /path/to/Samples_Organised/metadata_index.sqlite
```

When a catalog was created from a USB stick and the copied folders are not present, provide the current USB mount root for playback:

```bash
sample-key-indexer-web /path/to/SampleIndexes/USB_01/metadata_index.sqlite --library-root usb_01=/Volumes/USB_01/Samples
```

When playback should come from an organised `Key/` and `Unsorted/` tree, provide that root instead:

```bash
sample-key-indexer-web /path/to/SampleIndexes/USB_01/metadata_index.sqlite --destination-root usb_01=/Volumes/USB_01/SAMPLEZ
```

The browser remains searchable when the USB is not mounted. Refresh the browser after plugging the USB in and matching files will become playable.

You can also open multiple catalogs at once:

```bash
sample-key-indexer-web /path/to/SampleIndexes/USB_01/metadata_index.sqlite /path/to/SampleIndexes/USB_02/metadata_index.sqlite
```

For multi-device browsing, pass the mounted source or organised roots for any devices that are currently plugged in. The browser shows each loaded library, how much audio is playable or missing, and filters for Library and Playback:

```bash
sample-key-indexer-web \
  /path/to/SampleIndexes/USB_01/metadata_index.sqlite \
  /path/to/SampleIndexes/SD_02/metadata_index.sqlite \
  --destination-root usb_01=/Volumes/USB_01/SAMPLEZ \
  --library-root sd_02=/Volumes/SD_02/Samples
```

Summarize files that need review:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite
```

Preview the V3.3 deep-review candidate queue:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite --deep-plan --limit 100
```

Rerun only selected low-confidence, warning, error, or disagreement records:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite \
  --deep-rerun \
  --library-root library_id=/Volumes/USB/source_samples \
  --limit 500 \
  --report-json /path/to/deep_review_report.json
```

Use `--dry-run` with `--deep-rerun` to preview counts without changing metadata.
Real deep reruns analyze each selected file in an isolated worker process. If deep/balanced analysis crashes, the file is retried once with the safer `fast`/`librosa` path before being counted as a failed worker crash.
Use `--report-json` to save missing-audio examples, analysis errors, worker crash failures, and fallback successes for follow-up.
V3.4 records files that crash both the primary and fallback rerun in `analysis.deep_review` and skips those known failures by default. Pass `--retry-deep-failed` when you intentionally want to try them again after changing engines, dependencies, or analysis settings.

Check required KeyFinder and optional deep backend availability before installing or wiring new engines:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite --backend-check
```

Run the first KeyFinder-only experiment against recorded deep-review failures:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite \
  --keyfinder-experiment \
  --keyfinder-json /path/to/keyfinder_experiment.json
```

To run KeyFinder across a whole selected index instead of only deep-review failures:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite \
  --keyfinder-experiment \
  --keyfinder-scope all \
  --keyfinder-convert-retry \
  --keyfinder-json /path/to/keyfinder_all.json
```

Store KeyFinder as the required external comparison signal without changing the main key decision:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite \
  --keyfinder-enrich \
  --keyfinder-scope all \
  --keyfinder-convert-retry \
  --keyfinder-json /path/to/keyfinder_enrich_report.json
```

This writes KeyFinder details under `analysis.external.keyfinder`, including the raw key, normalized key, root, stored-key/root match flags, conversion status, errors, and update time. It does not overwrite `musical.key`, `musical.root`, `analysis.final_decision`, routing metadata, or copied files.

Recent quality-policy tuning:

- `filename_bpm_anchor` is no longer added as a review reason for obvious drum/noise sample types such as `DrumLoops`, `Kick`, `Snare`, `Hat`, `Perc`, `FX`, and `FXLoops`.
- known Python stdlib AIFF deprecation warnings (`aifc`, `audioop`, `sunau`) are ignored instead of being stored as analysis warnings.
- `short_signal_fft_adjusted` is kept in metadata but treated as informational rather than counting as an actionable warning in the main run summary.

Compare stored KeyFinder results against the current stored key/root decisions:

```bash
sample-key-indexer-review /path/to/Samples_Organised/metadata_index.sqlite \
  --keyfinder-compare \
  --examples 20 \
  --keyfinder-json /path/to/keyfinder_compare.json
```

This report is read-only. It summarizes stored KeyFinder metadata by library, sample type, confidence bucket, status, and match/disagreement decision.

Apply the V3.6 KeyFinder review-only policy:

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --keyfinder-apply-review \
  --keyfinder-review-threshold 0.75 \
  --keyfinder-json /path/to/keyfinder_review_policy.json
```

This does not change `musical.key`, `musical.root`, `analysis.final_decision`, confidence, routing, or copied files. It only adds a review reason for high-confidence stored key/root decisions that strongly disagree with successful KeyFinder metadata.

If the console script has not been refreshed yet, run it as a module:

```bash
python -m sample_key_indexer.web_app /path/to/Samples_Organised/metadata_index.json
python -m sample_key_indexer.review_report /path/to/Samples_Organised/metadata_index.sqlite
```

Enrich an existing index with the structured V1 feature schema without copying files again:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --force --dry-run
```

## Output

Detected samples are routed under:

```text
Samples_Organised/
  Key/
    E_minor/
      OneShots/
        Drums/
          Kick/
          Snare/
          Hat/
          Perc/
        Bass/
        Chords/
        Leads/
        Pads/
        Plucks/
        Vocals/
        FX/
      Loops/
        DrumLoops/
        BassLoops/
        MelodyLoops/
        VocalLoops/
        FXLoops/
```

Files with no usable root/key are routed under:

```text
Samples_Organised/
  Unsorted/
```

Metadata is written to the V2 SQLite index and exported as JSON:

```text
Samples_Organised/metadata_index.sqlite
Samples_Organised/metadata_index.json
```

The index is resumable: files with the same path, size, and modification time are skipped unless `--force` is passed.

New records use a structured V1 feature schema with:

- `file`: path, relative path, name, format, duration, sample rate, size, modified time
- `library`: source library ID, display name, and root path
- `musical`: root, key, scale confidence, notes, simple chord hints, BPM
- `audio_features`: loudness, frequency, timbre buckets, MFCC averages
- `classification`: category, type, subtype, source, confidence
- `analysis`: raw librosa decisions, Essentia decisions, selected engines, warnings, and the final decision used for routing

The web app can read both this structured schema and older flat records.

## V3 Ideas

- Add `ffprobe` for better file probing and skip decisions before loading audio into the analysis engines.
- Use KeyFinder CLI as the required external key-comparison backend.
- Consider Sonic Annotator with QM Vamp Plugins as a later optional deep harmonic analysis backend.
- Consider `aubio` for better onset and tempo utilities if we want a small dependency footprint.
- Add a deep review mode that reruns only low-confidence or disagreement cases instead of reprocessing the whole library.

## V3.1 Bulk Run Quality

- Python library warnings are captured into per-file analysis metadata instead of flooding the terminal.
- Ultra-short and near-silent audio gets a lightweight metadata result instead of full key, BPM, and spectral analysis.
- The final report includes error, review, low-confidence, key-disagreement, decoder-fallback, tiny-audio, and warning counts.

## V3.2 File Probing

- Duration probing uses `ffprobe` first when available, with soundfile/librosa fallbacks in `auto` mode.
- The CLI has a `--probe-backend auto|ffprobe|python` switch for testing skip decisions.
- The final report includes a duration probe breakdown so failed probes and fallback use are visible.

## V3.3 Deep Review Mode

- `sample-key-indexer-review --deep-plan` selects records needing focused reanalysis.
- `sample-key-indexer-review --deep-rerun` reprocesses only selected records and upserts them into the existing index.
- Deep reruns preserve library IDs, relative paths, and existing routing destinations so removable-drive catalogs keep working.
- Drum, percussion, and FX records are not selected just for weak key confidence; they need warnings or errors to enter the deep-review queue. This uses both stored type labels and obvious path/name tokens, so misclassified percussion folders do not flood harmonic review.
- Deep reruns isolate each selected file in a worker process and retry crashes with a `fast`/`librosa` fallback.
- `--report-json` writes a deep-review rerun report with counts and examples for missing audio, analysis errors, worker crash failures, and fallback successes.

## V3.4 Deep Review Failure Management

- Files that crash both the primary and fallback deep-review rerun are marked in `analysis.deep_review`.
- Normal deep-review plans skip known failed files so reruns do not keep getting stuck at the same candidates.
- `--retry-deep-failed` includes previously failed records when retesting after engine, dependency, or analysis setting changes.

## V3.5 Failure Reporting and Backend Triage

- `sample-key-indexer-review --deep-failures` prints a summary of files marked `analysis.deep_review.failed`.
- `--failures-json` and `--failures-csv` export deep-review failures for spreadsheet or later backend analysis.
- Failure reports summarize failed rerun files by reason, library, format, type, duration bucket, and path family.
- Reports include lightweight triage hints when failures share a clear pattern, such as all files being short WAVs that crash the deep librosa+essentia path.
- Use these reports to decide whether Sonic Annotator/QM Vamp Plugins, aubio, or pre-conversion/probing work should come next.

## V3.6 Deep Backend Experiments

- `sample-key-indexer-review --backend-check` prints a read-only report of required KeyFinder availability and optional deep backend availability.
- The check requires KeyFinder CLI and also looks for Sonic Annotator, QM Vamp Plugins in standard macOS/Homebrew Vamp paths, and aubio.
- The report includes the current deep-review failure target summary so external backend experiments stay scoped to real failures.
- `--keyfinder-experiment` runs KeyFinder CLI against recorded deep-review failures and reports successes, errors, and stored-key/root matches without changing metadata.
- `--keyfinder-enrich` runs the same KeyFinder path and stores its output under `analysis.external.keyfinder` without changing the main key decision or routing.
- `--keyfinder-enrich` shows a live progress bar when `tqdm` is available so long whole-library passes have a visible heartbeat.
- `--keyfinder-compare` is a read-only report over stored `analysis.external.keyfinder` results, grouped by library, type, confidence bucket, status, and match/disagreement decision.
- `--keyfinder-scope failures|review|all` controls whether KeyFinder runs against known deep failures, review candidates, or the full selected index.
- `--keyfinder-convert-retry` retries KeyFinder failures by converting the source to a temporary 16-bit PCM WAV with ffmpeg.
- Current SD 02 Trad result: KeyFinder processed 4 of 5 deep failures, failed 1 file with a resampling error, and matched the stored root on 2 files.
- Full SD 02 Trad index result: KeyFinder processed 2,452 of 4,411 files, failed 1,959 files with the same resampling error, matched 779 stored keys, and matched 1,020 stored roots.
- With `--keyfinder-convert-retry`, the same full index processed all 4,411 files, converted 1,959 files, had zero remaining errors, matched 1,346 stored keys, and matched 2,041 stored roots.
- Full SD 02 Trad metadata enrichment result: 4,411 records updated under `analysis.external.keyfinder`, 1,959 conversion retries used, zero errors, 1,346 stored-key matches, and 2,041 stored-root matches.
- Full SD 02 Trad comparison result: 4,411 records with KeyFinder metadata, 0 missing, 4,411 successes, 1,346 stored-key matches, 2,041 stored-root matches, 695 root-only matches, and 2,370 key/root disagreements.
- KeyFinder is now the required stored comparison backend. It should not replace the main key decision until more libraries are compared.
- V3.6 KeyFinder policy: keep KeyFinder out of the final key/root/confidence/routing decision. Use it only as a stored comparison signal and, with `--keyfinder-apply-review`, as a review-only flag for high-confidence disagreements.
- Parked until more devices exist: enrich another real library and compare KeyFinder behavior across libraries.
- Current V3.6 focus: classification quality, prompted by USB 01 physical-device testing where misleading folders and weak type detection put drum fills, hats, beats, and loops into the wrong routed folders.

## V3.6 Classification Quality

- Filename evidence is weighted higher than folder evidence when deciding sample type, because real pack paths and previous sorted folders can be misleading.
- Folder evidence is still used as a weaker hint when the filename is vague.
- Loop-like filename tokens such as `fill`, `beat`, `bpm`, `loop`, `ptn`, and `riff` can keep short drum material in `Loops` instead of `OneShots`.
- Drum indicators such as `drum`, `beat`, `fill`, `roll`, `hat`, `kick`, and `snare` help keep drum material out of misleading melodic, lead, and FX buckets.
- Full arrangement files named `fullmix`, `full mix`, `musicloop`, or `music loop` are ignored by default, reported under `Not copied - ignored filename patterns`, and can be included with `--include-ignored-files`.
- `sample-key-indexer-review --classification-audit` scans an existing metadata index for suspicious stored category/type decisions before rebuilding organised audio folders.
- Key analysis and KeyFinder comparison are unchanged by this classification pass.

Example:

```bash
sample-key-indexer-review /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --classification-audit \
  --examples 50 \
  --classification-json /tmp/usb_01_classification_audit.json \
  --classification-csv /tmp/usb_01_classification_audit.csv
```

## V3.7 Multi-Library Browser

- The web app API returns per-library summaries with total, playable, missing, and playback-source counts.
- The browser has library cards plus Library and Playback filters so multiple USB/SD indexes can be loaded together while still showing which device audio is currently mounted.
- Playback metadata distinguishes stored source paths, mounted source roots, stored organised paths, mounted organised roots, and missing audio.

## Troubleshooting

If every metadata entry has `root_note: null`, `key: null`, `type: FX`, `duration: 0.0`, and an error like `No module named '_lzma'`, the audio backend did not load. On macOS with pyenv, install XZ/LZMA support and recreate the virtualenv:

```bash
brew install xz
pyenv uninstall 3.11.9
pyenv install 3.11.9
cd /Users/mohammedansir/DEV/Projects/sample-key-indexer
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --doctor
```

After fixing the environment, delete the bad `metadata_index.json` or rerun with `--force`; otherwise the resumable index may skip records that were created while analysis was failing.
