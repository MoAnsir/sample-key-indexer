# Sample Library Key Indexer

A practical V1 local CLI for scanning large sample libraries, estimating root notes and keys, classifying samples, and organising them primarily by musical key.

## Install

```bash
cd /Users/mohammedansir/DEV/sample-key-indexer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

`librosa` handles pitch and chroma analysis. `soundfile` is included for WAV/AIFF support; MP3 support depends on the audio backend available to librosa/audioread on your machine.

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

By default, files longer than 60 seconds are treated as full songs and skipped. This keeps the library focused on samples and avoids filling the output folder with long tracks. To change the threshold:

```bash
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --max-duration 90
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

If the console script has not been refreshed yet, run it as a module:

```bash
python -m sample_key_indexer.web_app /path/to/Samples_Organised/metadata_index.json
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

Metadata is written to:

```text
Samples_Organised/metadata_index.json
```

The index is resumable: files with the same path, size, and modification time are skipped unless `--force` is passed.

New records use a structured V1 feature schema with:

- `file`: path, name, format, duration, sample rate, size, modified time
- `musical`: root, key, scale confidence, notes, simple chord hints, BPM
- `audio_features`: loudness, frequency, timbre buckets, MFCC averages
- `classification`: category, type, subtype, source, confidence
- `analysis`: raw librosa decisions plus the final decision used for routing

The web app can read both this structured schema and older flat records.

## Troubleshooting

If every metadata entry has `root_note: null`, `key: null`, `type: FX`, `duration: 0.0`, and an error like `No module named '_lzma'`, the audio backend did not load. On macOS with pyenv, install XZ/LZMA support and recreate the virtualenv:

```bash
brew install xz
pyenv uninstall 3.11.9
pyenv install 3.11.9
cd /Users/mohammedansir/DEV/sample-key-indexer
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
sample-key-indexer /path/to/SampleLibrary /path/to/Samples_Organised --doctor
```

After fixing the environment, delete the bad `metadata_index.json` or rerun with `--force`; otherwise the resumable index may skip records that were created while analysis was failing.
