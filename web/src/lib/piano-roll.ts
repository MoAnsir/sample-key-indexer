// Pure logic for the sketch piano-roll editor (MPC Grid View model).
// All times are in beats; midi pitches are 0-127.

export interface RollNote {
  id: number;
  midi: number;
  start: number;
  duration: number;
  velocity: number;
}

export type SnapMode = "absolute" | "relative" | "off";

// Timing Correct divisions, in beats. "T" = triplet (2/3 of the straight value).
// stepsPerBar assumes 4/4 — shown in the UI so MPC users can think in steps.
export const TC_DIVISIONS: { label: string; beats: number; stepsPerBar: number }[] = [
  { label: "1/4", beats: 1, stepsPerBar: 4 },
  { label: "1/8", beats: 0.5, stepsPerBar: 8 },
  { label: "1/8T", beats: 1 / 3, stepsPerBar: 12 },
  { label: "1/16", beats: 0.25, stepsPerBar: 16 },
  { label: "1/16T", beats: 1 / 6, stepsPerBar: 24 },
  { label: "1/32", beats: 0.125, stepsPerBar: 32 },
  { label: "1/32T", beats: 1 / 12, stepsPerBar: 48 },
  { label: "1/64", beats: 0.0625, stepsPerBar: 64 },
];

export interface GridLine {
  beat: number;
  kind: "bar" | "beat" | "step";
}

/** Vertical gridlines for the roll: bar lines, beat lines, and step lines at the
 *  current TC division. Step lines are omitted when they'd be denser than minStepPx. */
export function buildGridLines(
  totalBeats: number,
  beatsPerBar: number,
  division: number,
  beatWidth: number,
  minStepPx = 6,
): GridLine[] {
  const lines: GridLine[] = [];
  for (let beat = 0; beat <= totalBeats; beat++) {
    lines.push({ beat, kind: beat % beatsPerBar === 0 ? "bar" : "beat" });
  }
  if (division > 0 && division * beatWidth >= minStepPx) {
    const epsilon = 1e-9;
    for (let beat = division; beat < totalBeats - epsilon; beat += division) {
      // skip positions that already have a bar/beat line
      if (Math.abs(beat - Math.round(beat)) < epsilon) continue;
      lines.push({ beat, kind: "step" });
    }
  }
  return lines;
}

export const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

const SCALE_INTERVALS: Record<string, number[]> = {
  major: [0, 2, 4, 5, 7, 9, 11],
  minor: [0, 2, 3, 5, 7, 8, 10],
};

export function midiToName(midi: number): string {
  const octave = Math.floor(midi / 12) - 1;
  return `${NOTE_NAMES[midi % 12]}${octave}`;
}

export function pitchClass(midi: number): string {
  return NOTE_NAMES[midi % 12];
}

export function scalePitchClasses(tonic: string, mode: string): Set<number> {
  const root = NOTE_NAMES.indexOf(tonic);
  const intervals = SCALE_INTERVALS[mode] ?? SCALE_INTERVALS.minor;
  if (root < 0) return new Set(intervals);
  return new Set(intervals.map((i) => (root + i) % 12));
}

export interface RowSpec {
  midi: number;
  name: string;
  isRoot: boolean;
  inScale: boolean;
}

/** Rows for the grid, highest pitch first (like a piano roll). */
export function buildRows(
  tonic: string,
  mode: string,
  lowMidi: number,
  highMidi: number,
  chromatic: boolean,
): RowSpec[] {
  const classes = scalePitchClasses(tonic, mode);
  const rootClass = NOTE_NAMES.indexOf(tonic);
  const rows: RowSpec[] = [];
  for (let midi = highMidi; midi >= lowMidi; midi--) {
    const inScale = classes.has(midi % 12);
    if (!chromatic && !inScale) continue;
    rows.push({
      midi,
      name: midiToName(midi),
      isRoot: midi % 12 === rootClass,
      inScale,
    });
  }
  return rows;
}

/** Snap a beat position according to the snap mode.
 *  relative: preserves the offset of `origin` from its nearest gridline (MPC Relative snap). */
export function snapBeat(
  beat: number,
  division: number,
  mode: SnapMode,
  origin: number = 0,
): number {
  if (mode === "off" || division <= 0) return beat;
  if (mode === "relative") {
    const offset = origin - Math.round(origin / division) * division;
    return Math.round((beat - offset) / division) * division + offset;
  }
  return Math.round(beat / division) * division;
}

export function clampNote(note: RollNote, totalBeats: number): RollNote {
  const start = Math.min(Math.max(0, note.start), Math.max(0, totalBeats - note.duration));
  const duration = Math.min(note.duration, totalBeats - start);
  return {
    ...note,
    start,
    duration: Math.max(1 / 32, duration),
    midi: Math.min(127, Math.max(0, note.midi)),
    velocity: Math.min(127, Math.max(1, Math.round(note.velocity))),
  };
}

let nextId = 1;

export function makeNote(
  midi: number,
  start: number,
  duration: number,
  velocity = 100,
): RollNote {
  return { id: nextId++, midi, start, duration, velocity };
}

/** Pencil-tool click on an empty cell: add a note one division long. */
export function addNote(
  notes: RollNote[],
  midi: number,
  beat: number,
  division: number,
  snapMode: SnapMode,
  totalBeats: number,
  velocity = 100,
): RollNote[] {
  const start = snapMode === "off" ? beat : Math.floor(beat / division) * division;
  const duration = division > 0 ? division : 0.25;
  const note = clampNote(makeNote(midi, start, duration, velocity), totalBeats);
  return [...notes, note];
}

export function eraseNote(notes: RollNote[], id: number): RollNote[] {
  return notes.filter((n) => n.id !== id);
}

export function moveNote(
  notes: RollNote[],
  id: number,
  newMidi: number,
  newStart: number,
  division: number,
  snapMode: SnapMode,
  totalBeats: number,
): RollNote[] {
  return notes.map((n) => {
    if (n.id !== id) return n;
    const snapped = snapBeat(newStart, division, snapMode, n.start);
    return clampNote({ ...n, midi: newMidi, start: snapped }, totalBeats);
  });
}

export function resizeNote(
  notes: RollNote[],
  id: number,
  newDuration: number,
  division: number,
  snapMode: SnapMode,
  totalBeats: number,
): RollNote[] {
  return notes.map((n) => {
    if (n.id !== id) return n;
    let duration = newDuration;
    if (snapMode !== "off" && division > 0) {
      duration = Math.max(division, Math.round(duration / division) * division);
    }
    return clampNote({ ...n, duration }, totalBeats);
  });
}

export function setVelocity(notes: RollNote[], id: number, velocity: number): RollNote[] {
  return notes.map((n) =>
    n.id === id ? { ...n, velocity: Math.min(127, Math.max(1, Math.round(velocity))) } : n,
  );
}

/** Transpose selected notes by semitones (MPC bottom-bar Transpose). */
export function transposeNotes(
  notes: RollNote[],
  ids: Set<number>,
  semitones: number,
): RollNote[] {
  return notes.map((n) =>
    ids.has(n.id) ? { ...n, midi: Math.min(127, Math.max(0, n.midi + semitones)) } : n,
  );
}

/** Duplicate selected notes immediately after their span (MPC Shift+Duplicate). */
export function duplicateNotes(
  notes: RollNote[],
  ids: Set<number>,
  totalBeats: number,
): RollNote[] {
  const selected = notes.filter((n) => ids.has(n.id));
  if (selected.length === 0) return notes;
  const startMin = Math.min(...selected.map((n) => n.start));
  const endMax = Math.max(...selected.map((n) => n.start + n.duration));
  const span = endMax - startMin;
  const copies = selected
    .filter((n) => n.start + span < totalBeats - 1e-9)
    .map((n) => clampNote(makeNote(n.midi, n.start + span, n.duration, n.velocity), totalBeats));
  return [...notes, ...copies];
}

/** Convert API note_events (from a saved sketch or MIDI import) → RollNote[].
 *  Pitch may be a MIDI integer or a note-name string ("C#3", "Eb", 60).
 *  IDs start at `startId` (default 1) to avoid stale-counter collisions when
 *  loading pre-existing notes into an editor session. */
export function fromNoteEvents(
  events: { note: string | number; start: number; duration: number; velocity?: number }[],
  startId = 1,
): RollNote[] {
  let id = startId;
  const notes: RollNote[] = [];
  for (const ev of events) {
    let midi: number;
    if (typeof ev.note === "number") {
      midi = ev.note;
    } else {
      // Note name with optional octave, e.g. "C#3", "Eb", "d#2"
      const clean = ev.note.trim().replace(/^([A-Ga-g][b#]?)(-?\d+)?$/, (_, pc: string, oct: string) => {
        const flat: Record<string, string> = { Db: "C#", Eb: "D#", Gb: "F#", Ab: "G#", Bb: "A#" };
        const name = (pc[0].toUpperCase() + pc.slice(1));
        const sharp = flat[name] ?? name;
        const octave = oct != null ? parseInt(oct, 10) : 2;
        const idx = NOTE_NAMES.indexOf(sharp);
        if (idx < 0) return "-1";
        return String((octave + 1) * 12 + idx);
      });
      midi = parseInt(clean, 10);
    }
    if (isNaN(midi) || midi < 0 || midi > 127) continue;
    notes.push({
      id: id++,
      midi,
      start: ev.start,
      duration: Math.max(1 / 32, ev.duration),
      velocity: Math.min(127, Math.max(1, Math.round(ev.velocity ?? 100))),
    });
  }
  return notes;
}

/** Convert editor notes to the API's note_events payload shape. */
export function toNoteEvents(
  notes: RollNote[],
): { note: number; start: number; duration: number; velocity: number }[] {
  return [...notes]
    .sort((a, b) => a.start - b.start || a.midi - b.midi)
    .map((n) => ({
      note: n.midi,
      start: n.start,
      duration: n.duration,
      velocity: n.velocity,
    }));
}
