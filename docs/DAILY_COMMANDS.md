# Daily Commands

Run these from the project folder:

```bash
cd /Users/mohammedansir/DEV/Projects/sample-key-indexer
```

If the commands are missing after code changes:

```bash
pip install -e .
```

This installs the normal analysis stack, including Essentia. KeyFinder CLI is required too, but it is an external command-line tool, so install it separately and make sure one of these works:

```bash
which keyfinder-cli || which keyfinder
```

## Start The Browser

Metadata only, audio not mounted:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite
```

Original samples on the Mac or mounted source folder:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  --library-root sd_02_trad_v32_probe="/Users/mohammedansir/Desktop/Samples_to_detect/SAMPLES/Big.Fish.Audio.Indian.Traditions.Rex2.Wav"
```

Organised USB/SD device with `Key/` and `Unsorted/` folders:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --destination-root usb_01="/Volumes/SSK Drive/SAMPLEZ"
```

Multiple libraries at once:

```bash
sample-key-indexer-web \
  /Users/mohammedansir/Desktop/SampleIndexes/sd_02_trad_v32_probe/metadata_index.sqlite \
  /Users/mohammedansir/Desktop/SampleIndexes/usb_01/metadata_index.sqlite \
  --library-root sd_02_trad_v32_probe="/Users/mohammedansir/Desktop/Samples_to_detect/SAMPLES/Big.Fish.Audio.Indian.Traditions.Rex2.Wav" \
  --destination-root usb_01="/Volumes/SSK Drive/SAMPLEZ"
```

If port `8765` is busy, stop the old server with `Ctrl-C`, or use:

```bash
sample-key-indexer-web INDEX.sqlite --port 8766
```

## Analyse Samples On The Mac

Use this when the source samples are temporarily on the Mac and you want metadata only:

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

Replace:

- `LIBRARY_ID` with a stable ID like `usb_02` or `sd_03_trad`
- `Human Library Name` with the name you want shown in the browser

Use this when you want to create `Key/` and `Unsorted/` folders that you can move onto a USB or SD card:

```bash
caffeinate -dimsu sample-key-indexer \
  /Users/mohammedansir/Desktop/Samples_to_detect \
  /Users/mohammedansir/Desktop/Samples_organised/LIBRARY_ID \
  --library-id LIBRARY_ID \
  --library-name "Human Library Name" \
  --analysis-profile balanced \
  --engines librosa,essentia \
  --workers 4 \
  --write-every 25 \
  --probe-backend auto
```

The output folder will contain `Key/`, `Unsorted/`, `metadata_index.sqlite`, and `metadata_index.json`. Move the `Key/` and `Unsorted/` folders to the physical USB or SD card, and keep the metadata index on the Mac under `SampleIndexes`.

Kitchen sink: analyse from the Mac, organise into `Key/` and `Unsorted/`, use balanced Librosa + Essentia, skip long/fullmix material by default, probe with ffprobe when available, and write metadata as it goes:

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
```

After it finishes, move `/Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/Key` and `/Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/Unsorted` to the USB/SD device. Keep `metadata_index.sqlite` and `metadata_index.json` on the Mac so the browser can search the library without the device mounted.

## Rerun Specific Analysis

Preview what would be selected for deep rerun:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/metadata_index.sqlite \
  --deep-plan \
  --limit 25
```

Rerun selected low-confidence/review files:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/metadata_index.sqlite \
  --deep-rerun \
  --library-root LIBRARY_ID="/path/to/source/samples" \
  --limit 25 \
  --write-every 5 \
  --report-json /tmp/deep_review_report.json
```

If the audio is on an organised USB/SD device instead of the original source folder:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/metadata_index.sqlite \
  --deep-rerun \
  --destination-root LIBRARY_ID="/Volumes/DEVICE/SAMPLEZ" \
  --limit 25 \
  --write-every 5 \
  --report-json /tmp/deep_review_report.json
```

## Rerun KeyFinder Only

Add required KeyFinder comparison metadata without changing the final key:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/metadata_index.sqlite \
  --keyfinder-enrich \
  --keyfinder-scope all \
  --keyfinder-convert-retry \
  --write-every 25 \
  --keyfinder-json /tmp/keyfinder_enrich.json
```

Compare stored KeyFinder results:

```bash
sample-key-indexer-review \
  /Users/mohammedansir/Desktop/SampleIndexes/LIBRARY_ID/metadata_index.sqlite \
  --keyfinder-compare \
  --examples 20 \
  --keyfinder-json /tmp/keyfinder_compare.json
```
