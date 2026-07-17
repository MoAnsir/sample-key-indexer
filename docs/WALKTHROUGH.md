# Sample Key Indexer — Walkthrough

A practical guide from first scan to finished sketch, step by step.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Scanning Your First Library](#2-scanning-your-first-library)
3. [Browsing Your Library](#3-browsing-your-library)
4. [Sample Detail & Musical Context](#4-sample-detail--musical-context)
5. [Creating a Sketch](#5-creating-a-sketch)
6. [Drawing Notes on the Piano Roll](#6-drawing-notes-on-the-piano-roll)
7. [Using the Synth Preview](#7-using-the-synth-preview)
8. [Building an Arrangement](#8-building-an-arrangement)
9. [Finding Matching Samples](#9-finding-matching-samples)
10. [Editing a Saved Sketch](#10-editing-a-saved-sketch)
11. [The MPC Round-Trip](#11-the-mpc-round-trip)

---

## 1. Getting Started

### Install

```bash
cd /path/to/sample-key-indexer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> **Production install** (frontend bundled, no npm needed):
> ```bash
> pip install .   # note: no -e
> ```
> The wheel includes a pre-built copy of the React UI. `pip install -e .` (editable mode) does not bundle the frontend — you need a separate `cd web && npm run build` step.

### Check your environment

Before scanning, verify the audio stack is working:

```bash
sample-key-indexer /any/path /any/output --doctor
```

This checks librosa, essentia, ffprobe, and KeyFinder. Missing tools are listed with install hints. The scan will still work without optional tools — you just get less analysis depth.

### Start the web UI

If you already have an index from a previous scan:

```bash
sample-key-indexer-web /path/to/metadata_index.sqlite
# Open http://127.0.0.1:8765
```

If you want live-reload during frontend development, run both:

```bash
# Terminal 1
sample-key-indexer-web /path/to/metadata_index.sqlite

# Terminal 2
cd web && npm run dev
# Open http://localhost:5173
```

---

## 2. Scanning Your First Library

### Option A — Scan from the web UI

The easiest way for most people. Open the browser, click **Scan from...** in the header, and follow the three-step wizard:

1. **Source folder** — use the server-side folder browser to pick the folder containing your samples. (The browser's native file picker can't expose absolute filesystem paths — the wizard walks your filesystem via the backend instead.)
2. **Mode** — choose:
   - *Catalog only* — index the files where they are, no copying. Best for USB sticks and external drives you don't want to reorganize.
   - *Organize* — index and copy samples into a clean `Key/Type/` folder structure at the destination you choose.
3. **Options** — set a library name, choose workers (start at 1; raise it once you know the library scans cleanly), and optionally enable dry run to preview without writing.

Progress is shown live. When it finishes, the new library card appears on the dashboard — no page refresh needed. The scan location is remembered and auto-loaded next time you start `sample-key-indexer-web`.

### Option B — Scan from the command line

For large libraries or scheduled runs:

```bash
# Catalog only (no file copying)
sample-key-indexer /Volumes/USB_01/Samples /path/to/Indexes/usb_01 \
  --catalog-only --library-id usb_01 --library-name "USB 01"

# Organize into Key/Type folders
sample-key-indexer ~/Music/MySamples ~/Desktop/Samples_Organised
```

Then start the web UI pointing at the resulting index:

```bash
sample-key-indexer-web /path/to/Indexes/usb_01/metadata_index.sqlite \
  --library-root usb_01=/Volumes/USB_01/Samples
```

`--library-root` is needed when the index was written with a catalog-only scan — it tells the server where to find the actual audio files for playback.

### If the scan crashes partway through

Just rerun the same command. Files with a matching path, size, and modification time are skipped. The indexer is fully resumable by default.

---

## 3. Browsing Your Library

Click a library card on the Dashboard to load it into the Browse tab.

### The filter bar

The filter bar at the top of the Browse tab lets you narrow down samples in real time:

- **Search** — type any part of a filename, path, or key. Results update as you type (debounced 300ms).
- **Project Key** — set this to the key of the track you're working on. A **Fit** column appears in the table: *Same key*, *Compatible* (relative/dominant/subdominant/parallel), *Out of key*, or *No key*.
- **Category / Type / Key / Source / BPM** — dropdown filters, all combinable.
- **Brightness / Warmth / Confidence** — range sliders for tonal and quality filtering.
- **Unsorted only** — shows only files the engine couldn't classify confidently.

### Navigating the table

- Click any column header to sort; click again to reverse.
- Use **↑** / **↓** arrow keys to move between rows, **Enter** to open the detail panel for the selected row, **Escape** to close it.
- Pagination controls are at the top and bottom. Change rows-per-page (100/250/500/1000) to suit your screen.

### Key colors

Every key has a unique color derived from its position on the circle of fifths. Harmonically related keys have similar hues — you can visually scan the table and spot which samples share a key family without reading the labels.

---

## 4. Sample Detail & Musical Context

Click any row to open the slide-over detail panel from the right.

What you'll find inside:

- **Audio player** — WaveSurfer waveform with play/pause. For AIFF files, the server transcodes to WAV on the fly (requires ffmpeg).
- **Metadata grid** — key, root note, BPM, confidence, duration, format, sample rate, category, type, timbre, loudness.
- **Piano keyboard** — root note and detected notes highlighted in the key's color.
- **Circle of fifths** — the detected key as a colored wedge; compatible keys as lighter wedges; unrelated keys grey.
- **Compatible keys** — same key, relative, dominant, subdominant, and parallel, each with their diatonic chords listed.
- **Progressions** — chord progressions to try, with roman numerals and mood label. Each has a **⬇ MIDI** button — click it to download a `.mid` file you can drop straight onto the MPC.
- **Mood & transitions** — primary mood, supporting moods, and transition suggestions (e.g., "resolves tension" or "builds energy").
- **Review diagnostics** — if the sample was flagged for review, a collapsible section shows which engines disagreed and why, with comparison tables and CLI commands to investigate further.

Click **Mark Reviewed** to clear a sample from the review queue. This updates the SQLite index on disk immediately.

---

## 5. Creating a Sketch

A sketch is a musical idea you describe manually — no audio needed. You give it a key, BPM, and optional notes, and it receives the same analysis your scanned samples get: compatible keys, chord progressions, mood, and transitions.

Click **✏ New Sketch** in the header. The sketch editor opens as a full page with three steps.

### Step 1 — Details

Fill in:
- **Name** — anything you like.
- **Key / Tonic** — uses MPC-style flat/sharp labels (e.g., "D# / Eb"). Pick the root note you played in.
- **Mode** — Major or Minor.
- **BPM** — the tempo you recorded at.
- **Bars** — how many bars your pattern is.
- **Beats / bar** — 4 for standard time, 3 for waltz, etc.
- **Type** — what kind of part it is (Bass, Lead, Pad, Chord, Melody, Arp, Drum, …). This matters for cross-matching — the engine uses it to suggest complementary samples.
- **Frequency register** — optional; Sub, Low, Mid, or High. Useful for cross-matching when type alone isn't specific enough.

Click **Next** when done.

### Step 2 — Notes (optional)

If you want analysis that reflects your actual melody (out-of-scale warnings, note-aware progressions), enter the notes here. If you skip this step, the analysis uses only the key and mode you supplied.

See [section 6](#6-drawing-notes-on-the-piano-roll) for the full piano roll guide.

Click **Next** when done.

### Step 3 — Analysis

The analysis runs automatically when you reach this step. It shows:

- **Key confirmation** — the engine agrees with (or gently disputes) your stated key based on the notes you entered.
- **Out-of-scale notes** — any notes that don't belong to your stated key, flagged by name.
- **Compatible keys** — the five related keys you can safely blend with.
- **Progressions** — chord progressions that fit your key and mood, with roman numerals and MIDI download.
- **Mood profile** — primary mood, supporting moods, transition suggestions.

Hit **⬇ Download MIDI** to export your note events as a `.mid` file — ready to load back onto the MPC as a pattern.

Hit **Save Sketch** to persist it. The sketch appears as a **✏** card on the dashboard (dashed border) and as a row in the Browse table with a **✏ Sketch** status badge.

---

## 6. Drawing Notes on the Piano Roll

The piano roll in Step 2 is modeled on the MPC's Grid View.

### Tools

Three tools in the toolbar:

- **Pencil** — click an empty cell to add a note; click and drag right to set its length. Click an existing note to move it (drag horizontally). Drag the right edge of a note to resize it.
- **Eraser** — click any note to delete it. Double-clicking with the Pencil tool also erases.
- **Select** — click to select a note (highlighted border); Shift-click to multi-select. Drag a selection to move the group.

### Scale rows

By default, only rows in your stated scale are shown — the same as Pad Perform mode on the MPC. Root notes are highlighted in red like root pads. Toggle **Chromatic** to show all 12 notes.

### Time divisions

The **T.C.** selector sets the grid resolution, labeled in step terms:
- `1/8 · 8 steps/bar` — coarse; good for chords and bass
- `1/16 · 16 steps/bar` — standard
- `1/32 · 32 steps/bar` — fine; good for 16th-note fills
- `1/64 · 64 steps/bar` — maximum resolution
- Triplet variants (`1/8T`, `1/16T`, `1/32T`) for swing feels

Step gridlines redraw to match the selected division.

### Snap

Three snap modes:

- **Absolute** — notes snap to the nearest grid step.
- **Relative** — notes maintain their offset from the grid as you drag.
- **Off** — free positioning (fractions of a step).

### Velocity lane

Below the note grid, a velocity lane shows a small slider per note. Drag a slider up or down to change velocity (0–127). Louder notes appear taller.

### Editing shortcuts

- **Transpose** — ±1 semitone buttons shift all selected notes (or all notes if none selected) up or down.
- **Octave shift** — shift selected notes up or down an octave.
- **Duplicate** — copies selected notes and places them immediately after.
- **Clear** — removes all notes.

---

## 7. Using the Synth Preview

After analysis, a **Synth Preview** section appears in the results when your sketch has notes. This lets you hear your pattern played back through a browser synthesiser — no audio files required.

### Transport

Three buttons:

- **▶ Play** — plays the note events from your sketch at the sketch BPM. Each note triggers through the synth signal chain.
- **■ Stop** — stops immediately and clears any scheduled notes.
- **↻ Loop** — toggles loop mode. When enabled, playback restarts automatically at the end of the last bar.

AudioContext is created on play and released on stop, so the browser won't block permissions.

### OSC — Oscillator

- **Waveform** — four buttons: Sine (smooth, clean), Triangle (mellow with harmonics), Square (buzzy, hollow), Sawtooth (bright, aggressive). Default is Square.

### FILTER — Low-Pass Filter

- **Cutoff** — controls which frequencies pass through. The knob is log-scaled (80 Hz to 18 kHz) so the musically useful range isn't cramped in the bottom corner. Default is around 2.4 kHz — dark and full.
- **Resonance** — boosts the frequency right at the cutoff point. High resonance (right side) creates a synth-typical "honk." Default is low (0.12).

### ENV — ADSR Envelope

The envelope shapes how each note's volume evolves over time:

- **Attack** — time from silence to peak volume (0 to 2 seconds). Short = punchy, long = pad-like fade-in.
- **Decay** — time from peak down to the sustain level. Adds snap or softness.
- **Sustain** — the volume level held while the note is active (0 = cuts immediately after decay, 1 = stays at peak). Default 0.60.
- **Release** — time to fade after note-off (the note's duration ends). Longer release = more blur between notes.

### AMP — Master Volume

- **Volume** — overall output level (0 to 1). Default 0.65. Turn down if you're getting clipping; turn up if you want to reference against other sound sources.

### Tips

- Try **Sine + long Attack + high Sustain** for a pad sound.
- Try **Sawtooth + high Cutoff + short Attack** for a lead.
- Try **Square + low Cutoff + medium Resonance** for a bass.
- The synth plays your exact note events, velocities included — velocity scales the peak gain per note, so harder-hit notes (from the velocity lane) are louder.

---

## 8. Building an Arrangement

The **Arrangement Engine** section appears below Synth Preview in the results. It takes your 4-bar (or however long) pattern and expands it to a longer arrangement with musical variation.

### Controls

**Length** — how many bars the arrangement should be: 8, 12, 16, or 32.

**Strategies** — tick any combination:

- **Humanize** — adds subtle velocity variation per note (seeded, so the result is reproducible). Makes the pattern feel less quantized.
- **A/B Sections** — the second half of the arrangement is transposed up a diatonic 4th (the same interval as a classic "lift"). A section uses the original, B section uses the transposed version.
- **Fill** — on the last beat of selected sections, a rhythmic fill replaces the usual pattern — useful for transitional moments.
- **Breakdown** — creates a sparse section (root note only, first beat of each bar) for a drop or buildup.

Click **Build Arrangement**. The engine returns a section map showing each section as a chip:

- **A** (blue) — original pattern
- **B** (indigo) — transposed variation
- **Fill** (amber) — rhythmic fill section
- **Breakdown** (grey) — sparse drop section

Stats below the map show total bars, BPM, tonic/mode, and total note count.

Click **⬇ Download Arrangement MIDI** to get a flat single-track `.mid` file. It's designed for MPC compatibility — all sections are written sequentially into one track with correct bar-offset timing, so you can import it as a pattern of the full length.

---

## 9. Finding Matching Samples

The **Match Panel** appears below Arrangement in the results. It searches your loaded sample library and ranks samples by how well they complement the sketch.

### Before you start

The cross-match runs against the samples currently loaded in the server's memory — the same set you see in the Browse table. If you haven't loaded a library yet, you'll see a prompt to go to the Dashboard first and click a library card.

### How scoring works

Four dimensions, each independently toggleable:

| Dimension | Weight | What it checks |
|-----------|--------|---------------|
| **Key** | 40% | Same key = 1.0, relative/dominant/subdominant = 0.7–0.5, other = 0 |
| **Frequency slot** | 25% | Does the sample's type fill a different frequency range than your sketch? (e.g., a Bass sketch scores well against samples classified as Mid or High) |
| **Mood** | 20% | Does the sample's brightness/warmth match the mood vocabulary from your sketch's analysis? |
| **BPM** | 15% | Within ±5 BPM = 1.0, within ±10 = 0.5, or halftime/doubletime match |

### Using the results

Toggle dimension checkboxes to re-weight the search in real time. Results update on the next "Find Matching Samples" click.

Each result row shows:
- Sample name, key, type, BPM
- A **score badge** (0.00–1.00) showing the overall match quality
- Colored **reason chips** showing which dimensions matched (e.g., "same key", "fills highs", "BPM ×2")

Click any row to open that sample in the detail panel — same panel as the Browse tab, with audio preview and full musical context.

---

## 10. Editing a Saved Sketch

Sketches are saved in `~/.sample-key-indexer/sketches.sqlite` and auto-load on every `sample-key-indexer-web` startup.

To reopen a sketch for editing:

- On the **Dashboard**, find the sketch's ✏ card and click **Edit**.
- In the **Browse table**, find the sketch row (it has a ✏ badge) and click **Edit** in the action column.

The sketch wizard opens on the notes step with all form fields pre-filled (key, BPM, bars, type, etc.) and the piano roll populated with the saved notes. Make any changes and click **Save Sketch** — the save is an upsert, so the existing sketch is updated in place (same ID, same dashboard card).

---

## 11. The MPC Round-Trip

The full workflow for users who compose on MPC hardware:

### Export from MPC → import into sketch

1. On the MPC, export your pattern as MIDI (Main → Pattern → Export MIDI, or similar depending on firmware version).
2. Transfer the `.mid` file to your Mac (USB, Dropbox, etc.).
3. In the sketch wizard, go to the Notes step. Drag and drop the `.mid` file onto the **Import MIDI** zone (or click to browse).
4. The parser reads BPM, time signature, and note events. BPM and bars are pre-filled; notes appear on the piano roll ready to edit.
5. Fill in Key/Mode/Type on the Details step (the MIDI file usually doesn't contain this), then step through to Analysis.

Supported: Type 0 and Type 1 MIDI. Notes from all tracks are merged into a single lane.

### Sketch MIDI → back to MPC

From the Analysis step:

- **Download MIDI** (the sketch notes button) — exports your exact note events. Load this as a MIDI pattern on the MPC to play with the same notes through any instrument.
- **Download Arrangement MIDI** (from the Arrangement Panel) — exports the full expanded arrangement as a single flat track. Import it as a longer pattern to continue building the track.

### Use cross-match to find samples that layer

After sketching a bass line, go to Match Panel and find kicks and hats that fit the BPM and frequency slot. When you find something you like, click the row and download its MIDI progression to see what chords the engine suggests for that sample — you might find a new direction for the track.
