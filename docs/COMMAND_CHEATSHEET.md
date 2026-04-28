# Sample Key Indexer Command Cheat Sheet

Use these from the project root:

```bash
cd /Users/mohammedansir/DEV/Projects/SampleApp/sample-key-indexer
```

After code changes, reinstall the editable package:

```bash
pip install -e .
```

This installs the normal analysis stack, including Essentia.

## Check The Setup

Check the audio analysis environment:

```bash
sample-key-indexer --doctor
```

Check the current branch and recent work:

```bash
git branch --show-current
git log --oneline -5
```

Run the test suite:

```bash
python3 -B -m unittest discover -s tests
```

## Catalog Health

When a USB/SD is not mounted, you can still browse metadata, but playback will be missing. To quantify this per library, run:

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --catalog-health \
  --destination-root "usb_01=/Volumes/SSK Drive/SAMPLEZ"
```

## Mark Reviewed

After you manually review a library, you can mark the current `needs_review` set as reviewed so it stops showing up in the review summary:

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite --mark-reviewed
```

## Review Denoise

Reduce non-actionable review noise (especially drums/FX disagreement reasons):

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite --review-denoise
```

## V3 Health

One compact dashboard view (catalog health + last run summary + top offenders):

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite --v3-health
```

## Index A New Device Or Folder

Sanitize a messy source folder in place before scanning (removes unsupported files, pack baggage like ReadMe/artwork/PDFs, Mac artifacts, full-arrangement mixes like `fullmix`/`main mix`/`musicloop`, common track-title baggage like `original mix` / `extended mix` / `radio edit` / `stereo mix` / `2track`, and long demo/song/track files when duration > 60s):

```bash
sample-key-indexer-sanitize /Users/mohammedansir/Desktop/Samples_to_detect
```

Optional: also remove/quarantine supported audio that ffprobe can't open (corrupt/unhandled):

```bash
sample-key-indexer-sanitize /Users/mohammedansir/Desktop/Samples_to_detect --remove-unopenable-audio
```

Catalog only, keeping audio where it is:

```bash
caffeinate -dimsu sample-key-indexer \
  /Users/mohammedansir/Desktop/Samples_to_detect \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID \
  --catalog-only \
  --library-id LIBRARY_ID \
  --library-name "Human Library Name" \
  --analysis-profile balanced \
  --engines librosa,essentia \
  --workers 4 \
  --write-every 25 \
  --probe-backend auto
```

Main indexing runs also write `analysis_run_report.json` in the output root. Use `--report-json /tmp/LIBRARY_ID_run_report.json` if you want to keep a named debug log elsewhere. The report now includes failed-probe reasons/examples, suspicious-file examples, and the explained source/output size delta too.

Kitchen sink, creating `Key/` and `Unsorted/` plus metadata for a physical USB/SD:

One command:

```bash
caffeinate -dimsu sample-key-indexer-kitchen-sink \
  /Users/mohammedansir/Desktop/Samples_to_detect \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID \
  --library-id LIBRARY_ID \
  --library-name "Human Library Name" \
  --analysis-profile balanced \
  --engines librosa,essentia \
  --workers 4 \
  --write-every 25 \
  --probe-backend auto \
  --keyfinder-convert-retry

Notes:
- For resumable reruns, use `--keyfinder-scope missing` (default) so KeyFinder skips samples that already have a successful KeyFinder result stored.
- You can parallelize KeyFinder with `--keyfinder-workers N` (start around 8-16; too high can become IO-bound).

# Speed up KeyFinder with parallel workers (start with 8):
#   --keyfinder-workers 8
```

This produces the normal `analysis_run_report.json` log during indexing, then enriches the finished index with KeyFinder comparison metadata (with a visible progress bar).

KeyFinder is resumable by default in kitchen sink (`--keyfinder-scope missing`). To force a full rerun:

```bash
sample-key-indexer-kitchen-sink /path/to/source /path/to/output --keyfinder-scope all --keyfinder-force
```

Run V4 deep analysis during kitchen sink (stores routed deep-analysis metadata in the index, including tonal/tuning, loop BPM/ticks, mono note events, and polyphonic note events where supported; reruns skip up-to-date samples automatically):

```bash
sample-key-indexer-kitchen-sink /path/to/source /path/to/output \
  --keyfinder-convert-retry \
  --keyfinder-workers 8 \
  --deep-analysis smart \
  --deep-analysis-scope musical
```

Plan deep analysis directly against an existing index:

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --deep-analysis-plan \
  --deep-analysis-mode smart \
  --deep-analysis-scope musical \
  --deep-analysis-json /tmp/deep_analysis_plan.json
```

Run the first real deep-analysis execution pass (stores routed deep metadata under `analysis.deep_analysis`, including tonal/tuning, loop BPM/ticks, mono note events, and polyphonic note events when the route uses Basic Pitch; reruns skip up-to-date samples automatically):

```bash
sample-key-indexer-review /path/to/metadata_index.sqlite \
  --deep-analysis-run \
  --deep-analysis-mode smart \
  --deep-analysis-scope musical \
  --library-root LIBRARY_ID=/mounted/source/root \
  --deep-analysis-json /tmp/deep_analysis_run.json
```

Two-step fallback (same behavior):

```bash
caffeinate -dimsu sample-key-indexer \
  /Users/mohammedansir/Desktop/Samples_to_detect \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID \
  --library-id LIBRARY_ID \
  --library-name "Human Library Name" \
  --analysis-profile balanced \
  --engines librosa,essentia \
  --workers 4 \
  --write-every 25 \
  --probe-backend auto

sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/metadata_index.sqlite \
  --keyfinder-enrich \
  --keyfinder-scope all \
  --keyfinder-convert-retry \
  --write-every 25 \
  --keyfinder-json /tmp/LIBRARY_ID_keyfinder_enrich.json
```

Example for the SD 02 Trad test library:

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

Include files normally skipped as fullmix/full mix:

```bash
sample-key-indexer INPUT_ROOT OUTPUT_ROOT --include-ignored-files
```

Ignored-name matching also covers `musicloop`, `music-loop`, `music_loop`, and `music loop`.

## Start The Web App

Metadata only, no mounted audio:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite
```

When you open a `.sqlite` index, the browser can also mark samples reviewed/unreviewed (it updates the SQLite index on disk). JSON indexes are browse-only.

Use original source audio on the Mac or a mounted source folder:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --library-root sd_02_trad_v32_probe="/Users/mohammedansir/Desktop/Samples_to_detect/SAMPLES/Big.Fish.Audio.Indian.Traditions.Rex2.Wav"
```

Use an organised USB/SD tree containing `Key/` and `Unsorted/`:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --destination-root usb_01="/Volumes/SSK Drive/SAMPLEZ"
```

Open multiple libraries at once:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --library-root sd_02_trad_v32_probe="/Users/mohammedansir/Desktop/Samples_to_detect/SAMPLES/Big.Fish.Audio.Indian.Traditions.Rex2.Wav" \
  --destination-root usb_01="/Volumes/SSK Drive/SAMPLEZ"
```

Auto-load every catalog under a directory (prefers `.sqlite` when both exist):

```bash
sample-key-indexer-web /Users/mohammedansir/Desktop/SampleIndexes
```

If port `8765` is already in use, stop the old server with `Ctrl-C` in its terminal, or run on another port:

```bash
sample-key-indexer-web INDEX.sqlite --port 8766
```

## Review And Quality Reports

Plan deep-review candidates without changing metadata:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --deep-plan \
  --limit 25
```

Rerun selected deep-review candidates:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --deep-rerun \
  --library-root sd_02_trad_v32_probe="/Users/mohammedansir/Desktop/Samples_to_detect/SAMPLES/Big.Fish.Audio.Indian.Traditions.Rex2.Wav" \
  --limit 25 \
  --write-every 5 \
  --report-json /tmp/deep_review_report.json
```

Report known deep-review failures:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --deep-failures \
  --examples 20 \
  --failures-json /tmp/deep_failures.json \
  --failures-csv /tmp/deep_failures.csv
```

Audit suspicious category/type decisions before rebuilding a physical device:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --classification-audit \
  --examples 50 \
  --classification-json /tmp/usb_01_classification_audit.json \
  --classification-csv /tmp/usb_01_classification_audit.csv
```

## KeyFinder

Check required KeyFinder and optional backend availability:

```bash
which keyfinder-cli || which keyfinder
```

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --backend-check
```

Store KeyFinder metadata for a library without changing the final key:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-enrich \
  --keyfinder-scope all \
  --keyfinder-convert-retry \
  --write-every 25 \
  --keyfinder-json /tmp/keyfinder_enrich.json
```

Compare stored KeyFinder metadata with current stored key/root decisions:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-compare \
  --examples 20 \
  --keyfinder-json /tmp/keyfinder_compare.json
```

Apply the V3.6 review-only KeyFinder policy:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-apply-review \
  --keyfinder-review-threshold 0.75 \
  --keyfinder-json /tmp/keyfinder_review_policy.json
```

Dry-run the same policy first:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --keyfinder-apply-review \
  --dry-run
```

## SQLite Checks

Count samples in an index:

```bash
sqlite3 /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  "select count(*) from samples;"
```

Check KeyFinder enrichment counts:

```bash
sqlite3 /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  "select count(*) as total,
          sum(case when json_extract(payload, '$.analysis.external.keyfinder.status') = 'success' then 1 else 0 end) as keyfinder_success,
          sum(case when json_extract(payload, '$.analysis.external.keyfinder.conversion_used') = 1 then 1 else 0 end) as conversion_used
   from samples;"
```

List review-only KeyFinder flags:

```bash
sqlite3 /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  "select json_extract(payload, '$.file.name'),
          json_extract(payload, '$.musical.key'),
          json_extract(payload, '$.analysis.external.keyfinder.normalized_key')
   from samples
   where json_extract(payload, '$.analysis.review.reasons') like '%keyfinder_high_confidence_disagreement%'
   limit 20;"
```

## Disk And Mount Checks

List mounted drives:

```bash
ls /Volumes
```

Check a folder size:

```bash
du -sh /Users/mohammedansir/Desktop/Samples_to_detect
```

Count files in a folder:

```bash
find /Users/mohammedansir/Desktop/Samples_to_detect -type f | wc -l
```
