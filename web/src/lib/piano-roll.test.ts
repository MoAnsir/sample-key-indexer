import { describe, it, expect } from "vitest";
import {
  addNote,
  buildGridLines,
  buildRows,
  clampNote,
  duplicateNotes,
  eraseNote,
  makeNote,
  midiToName,
  moveNote,
  resizeNote,
  scalePitchClasses,
  setVelocity,
  snapBeat,
  TC_DIVISIONS,
  toNoteEvents,
  transposeNotes,
} from "./piano-roll";

describe("midiToName", () => {
  it("names middle C and neighbours", () => {
    expect(midiToName(60)).toBe("C4");
    expect(midiToName(39)).toBe("D#2");
    expect(midiToName(24)).toBe("C1");
  });
});

describe("scalePitchClasses", () => {
  it("D# minor contains the right pitch classes", () => {
    const classes = scalePitchClasses("D#", "minor");
    // D# F F# G# A# B C#
    expect([...classes].sort((a, b) => a - b)).toEqual([1, 3, 5, 6, 8, 10, 11]);
  });

  it("C major is the white keys", () => {
    const classes = scalePitchClasses("C", "major");
    expect([...classes].sort((a, b) => a - b)).toEqual([0, 2, 4, 5, 7, 9, 11]);
  });
});

describe("buildRows", () => {
  it("scale-filtered rows only include scale notes", () => {
    const rows = buildRows("D#", "minor", 36, 47, false);
    expect(rows).toHaveLength(7); // one octave of the scale
    expect(rows.every((r) => r.inScale)).toBe(true);
  });

  it("chromatic shows all 12, flags out-of-scale rows", () => {
    const rows = buildRows("D#", "minor", 36, 47, true);
    expect(rows).toHaveLength(12);
    expect(rows.filter((r) => !r.inScale)).toHaveLength(5);
  });

  it("rows are ordered high to low and mark the root", () => {
    const rows = buildRows("C", "major", 48, 72, false);
    expect(rows[0].midi).toBeGreaterThan(rows[rows.length - 1].midi);
    const roots = rows.filter((r) => r.isRoot);
    expect(roots.every((r) => r.name.startsWith("C"))).toBe(true);
  });
});

describe("snapBeat", () => {
  it("absolute snaps to nearest gridline", () => {
    expect(snapBeat(1.1, 0.25, "absolute")).toBeCloseTo(1.0);
    expect(snapBeat(1.2, 0.25, "absolute")).toBeCloseTo(1.25);
  });

  it("relative preserves the origin's offset from the grid", () => {
    // origin 1.1 is +0.1 from gridline 1.0 (division 0.25)
    expect(snapBeat(1.9, 0.25, "relative", 1.1)).toBeCloseTo(1.85);
  });

  it("off returns the raw beat", () => {
    expect(snapBeat(1.2345, 0.25, "off")).toBe(1.2345);
  });

  it("supports triplet divisions", () => {
    expect(snapBeat(0.3, 1 / 3, "absolute")).toBeCloseTo(1 / 3);
  });
});

describe("clampNote", () => {
  it("keeps note inside the sequence", () => {
    const note = clampNote(makeNote(60, 31.5, 1), 32);
    expect(note.start + note.duration).toBeLessThanOrEqual(32);
  });

  it("clamps negative start to zero", () => {
    expect(clampNote(makeNote(60, -2, 1), 32).start).toBe(0);
  });

  it("clamps midi and velocity ranges", () => {
    const note = clampNote({ ...makeNote(200, 0, 1), velocity: 300 }, 32);
    expect(note.midi).toBe(127);
    expect(note.velocity).toBe(127);
  });
});

describe("addNote / eraseNote", () => {
  it("pencil click adds a note one division long at the cell start", () => {
    const notes = addNote([], 39, 1.9, 0.5, "absolute", 32);
    expect(notes).toHaveLength(1);
    expect(notes[0].start).toBeCloseTo(1.5); // floor to cell
    expect(notes[0].duration).toBeCloseTo(0.5);
    expect(notes[0].midi).toBe(39);
  });

  it("snap off keeps the raw click position", () => {
    const notes = addNote([], 39, 1.9, 0.5, "off", 32);
    expect(notes[0].start).toBeCloseTo(1.9);
  });

  it("eraseNote removes by id", () => {
    const notes = addNote([], 39, 0, 0.5, "absolute", 32);
    expect(eraseNote(notes, notes[0].id)).toHaveLength(0);
  });
});

describe("moveNote", () => {
  it("moves pitch and snapped start", () => {
    const notes = addNote([], 39, 0, 0.5, "absolute", 32);
    const moved = moveNote(notes, notes[0].id, 42, 2.1, 0.5, "absolute", 32);
    expect(moved[0].midi).toBe(42);
    expect(moved[0].start).toBeCloseTo(2.0);
  });

  it("does not touch other notes", () => {
    let notes = addNote([], 39, 0, 0.5, "absolute", 32);
    notes = addNote(notes, 42, 1, 0.5, "absolute", 32);
    const moved = moveNote(notes, notes[0].id, 40, 4, 0.5, "absolute", 32);
    expect(moved[1]).toEqual(notes[1]);
  });
});

describe("resizeNote", () => {
  it("snaps duration to division multiples", () => {
    const notes = addNote([], 39, 0, 0.5, "absolute", 32);
    const resized = resizeNote(notes, notes[0].id, 1.3, 0.5, "absolute", 32);
    expect(resized[0].duration).toBeCloseTo(1.5);
  });

  it("enforces a minimum of one division", () => {
    const notes = addNote([], 39, 0, 0.5, "absolute", 32);
    const resized = resizeNote(notes, notes[0].id, 0.01, 0.5, "absolute", 32);
    expect(resized[0].duration).toBeCloseTo(0.5);
  });
});

describe("setVelocity", () => {
  it("sets and clamps velocity", () => {
    const notes = addNote([], 39, 0, 0.5, "absolute", 32);
    expect(setVelocity(notes, notes[0].id, 90)[0].velocity).toBe(90);
    expect(setVelocity(notes, notes[0].id, 500)[0].velocity).toBe(127);
    expect(setVelocity(notes, notes[0].id, 0)[0].velocity).toBe(1);
  });
});

describe("transposeNotes", () => {
  it("transposes only selected ids", () => {
    let notes = addNote([], 39, 0, 0.5, "absolute", 32);
    notes = addNote(notes, 46, 1, 0.5, "absolute", 32);
    const out = transposeNotes(notes, new Set([notes[0].id]), 12);
    expect(out[0].midi).toBe(51);
    expect(out[1].midi).toBe(46);
  });
});

describe("duplicateNotes", () => {
  it("copies the selection immediately after its span", () => {
    let notes = addNote([], 39, 0, 0.5, "absolute", 32);
    notes = addNote(notes, 42, 1, 1, "absolute", 32);
    const ids = new Set(notes.map((n) => n.id));
    const out = duplicateNotes(notes, ids, 32);
    expect(out).toHaveLength(4);
    // span = 2 beats (0 -> 2), copies at +2
    expect(out[2].start).toBeCloseTo(2);
    expect(out[3].start).toBeCloseTo(3);
  });

  it("drops copies that would start past the end", () => {
    const notes = addNote([], 39, 31, 1, "absolute", 32);
    const out = duplicateNotes(notes, new Set([notes[0].id]), 32);
    expect(out).toHaveLength(1);
  });

  it("returns unchanged when nothing selected", () => {
    const notes = addNote([], 39, 0, 0.5, "absolute", 32);
    expect(duplicateNotes(notes, new Set(), 32)).toBe(notes);
  });
});

describe("TC_DIVISIONS", () => {
  it("covers MPC step resolutions from 4 to 64 steps per bar", () => {
    const steps = TC_DIVISIONS.map((d) => d.stepsPerBar);
    expect(steps).toEqual([4, 8, 12, 16, 24, 32, 48, 64]);
  });

  it("beats and stepsPerBar are consistent in 4/4", () => {
    for (const d of TC_DIVISIONS) {
      expect(d.beats * d.stepsPerBar).toBeCloseTo(4);
    }
  });
});

describe("buildGridLines", () => {
  it("marks bar and beat lines", () => {
    const lines = buildGridLines(8, 4, 0.25, 48);
    const bars = lines.filter((l) => l.kind === "bar").map((l) => l.beat);
    expect(bars).toEqual([0, 4, 8]);
    const beats = lines.filter((l) => l.kind === "beat").map((l) => l.beat);
    expect(beats).toEqual([1, 2, 3, 5, 6, 7]);
  });

  it("adds step lines between beats at the division", () => {
    const lines = buildGridLines(2, 4, 0.5, 48); // 1/8 steps
    const steps = lines.filter((l) => l.kind === "step").map((l) => l.beat);
    expect(steps).toEqual([0.5, 1.5]);
  });

  it("omits step lines when they would be too dense to see", () => {
    // 1/64 at 48px/beat = 3px spacing < 6px minimum
    const lines = buildGridLines(4, 4, 0.0625, 48);
    expect(lines.filter((l) => l.kind === "step")).toHaveLength(0);
  });

  it("keeps 1/64 steps when zoomed wide enough", () => {
    const lines = buildGridLines(1, 4, 0.0625, 120);
    expect(lines.filter((l) => l.kind === "step").length).toBeGreaterThan(0);
  });

  it("does not duplicate lines on whole beats", () => {
    const lines = buildGridLines(4, 4, 0.5, 48);
    const positions = lines.map((l) => l.beat);
    expect(new Set(positions).size).toBe(positions.length);
  });
});

describe("toNoteEvents", () => {
  it("emits API payload sorted by start", () => {
    let notes = addNote([], 46, 2, 0.5, "absolute", 32);
    notes = addNote(notes, 39, 0, 1, "absolute", 32, 88);
    const events = toNoteEvents(notes);
    expect(events[0]).toEqual({ note: 39, start: 0, duration: 1, velocity: 88 });
    expect(events[1].note).toBe(46);
  });
});
