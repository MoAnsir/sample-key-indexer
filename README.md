# Sample Library Key Indexer

A practical V1 local CLI for scanning large sample libraries, estimating root notes and keys, classifying samples, and organising them primarily by musical key.

For durable project context, architecture notes, workflows, branch state, and AI-agent memory, read [`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md).

## Install

```bash
cd /Users/mohammedansir/DEV/Projects/sample-key-indexer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

`librosa` handles the baseline pitch and chroma analysis. `soundfile` is included for WAV/AIFF support; MP3 support depends on the audio backend available to librosa/audioread on your machine.

V2 can compare against Essentia when it is installed:

```bash
pip install -e ".[v2]"
```

You can also install it directly with `pip install essentia`. If Essentia is not installed, the balanced V2 profile still runs and records a warning in the analysis metadata.

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

Build a searchable catalog without copying audio into `Key/` or `Unsorted`:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/SampleIndexes/USB_01 --catalog-only --library-id usb_01 --library-name "USB 01"
```

V2 uses the balanced analysis profile by default. It keeps the librosa baseline, tries optional Essentia key analysis when available, writes a SQLite working index, and exports the JSON metadata used by the browser:

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
  --limit 500
```

Use `--dry-run` with `--deep-rerun` to preview counts without changing metadata.

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
- `analysis`: raw librosa decisions, optional Essentia decisions, selected engines, warnings, and the final decision used for routing

The web app can read both this structured schema and older flat records.

## V3 Ideas

- Add `ffprobe` for better file probing and skip decisions before loading audio into the analysis engines.
- Consider KeyFinder or Sonic Annotator with QM Vamp Plugins as a deep harmonic analysis backend.
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
