import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PianoRoll from "./PianoRoll";
import { makeNote, type RollNote } from "../lib/piano-roll";

const onChange = vi.fn();

function renderRoll(notes: RollNote[] = []) {
  return render(
    <PianoRoll
      tonic="D#"
      mode="minor"
      bars={2}
      beatsPerBar={4}
      notes={notes}
      onChange={onChange}
    />,
  );
}

beforeEach(() => {
  onChange.mockReset();
});

describe("PianoRoll — layout", () => {
  it("renders the toolbar tools", () => {
    renderRoll();
    expect(screen.getByText("✏ Pencil")).toBeInTheDocument();
    expect(screen.getByText("⌫ Eraser")).toBeInTheDocument();
    expect(screen.getByText("▭ Select")).toBeInTheDocument();
  });

  it("renders TC divisions including triplets", () => {
    renderRoll();
    expect(screen.getByRole("option", { name: "1/8T" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "1/16" })).toBeInTheDocument();
  });

  it("renders snap modes Absolute/Relative/Off", () => {
    renderRoll();
    expect(screen.getByRole("option", { name: "Absolute" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Relative" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Off" })).toBeInTheDocument();
  });

  it("scale filter shows only D# minor rows; chromatic shows all", () => {
    renderRoll();
    // scale-filtered: no E natural rows visible
    expect(screen.queryByTestId("key-E2")).not.toBeInTheDocument();
    expect(screen.getByTestId("key-D#2")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Chromatic"));
    expect(screen.getByTestId("key-E2")).toBeInTheDocument();
  });

  it("marks root rows distinctly", () => {
    renderRoll();
    const rootKey = screen.getByTestId("key-D#2");
    expect(rootKey.className).toContain("text-red-400");
  });

  it("octave shift changes the visible range", () => {
    renderRoll();
    expect(screen.getByTestId("key-D#1")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Octave up"));
    expect(screen.queryByTestId("key-D#1")).not.toBeInTheDocument();
    expect(screen.getByTestId("key-D#4")).toBeInTheDocument();
  });
});

describe("PianoRoll — editing", () => {
  it("pencil click on the grid adds a note", () => {
    renderRoll();
    fireEvent.click(screen.getByTestId("roll-grid"), { clientX: 100, clientY: 30 });
    expect(onChange).toHaveBeenCalled();
    const notes = onChange.mock.calls[0][0] as RollNote[];
    expect(notes).toHaveLength(1);
    expect(notes[0].velocity).toBe(100);
  });

  it("eraser click on a note removes it", () => {
    const note = makeNote(39, 0, 1); // D#2 in scale rows
    renderRoll([note]);
    fireEvent.click(screen.getByText("⌫ Eraser"));
    fireEvent.click(screen.getByTestId(`note-${note.id}`));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("double-click erases with pencil tool", () => {
    const note = makeNote(39, 0, 1);
    renderRoll([note]);
    fireEvent.doubleClick(screen.getByTestId(`note-${note.id}`));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("clear removes all notes", () => {
    renderRoll([makeNote(39, 0, 1), makeNote(42, 1, 1)]);
    fireEvent.click(screen.getByText("Clear"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("transpose buttons disabled without selection, work after selecting", () => {
    const note = makeNote(39, 0, 1);
    renderRoll([note]);
    const up = screen.getByText("+1");
    expect(up).toBeDisabled();
    fireEvent.click(screen.getByTestId(`note-${note.id}`)); // select
    expect(up).not.toBeDisabled();
    fireEvent.click(up);
    const updated = onChange.mock.calls.at(-1)![0] as RollNote[];
    expect(updated[0].midi).toBe(40);
  });

  it("duplicate appends selection after its span", () => {
    const note = makeNote(39, 0, 1);
    renderRoll([note]);
    fireEvent.click(screen.getByTestId(`note-${note.id}`));
    fireEvent.click(screen.getByText("Duplicate"));
    const updated = onChange.mock.calls.at(-1)![0] as RollNote[];
    expect(updated).toHaveLength(2);
    expect(updated[1].start).toBeCloseTo(1);
  });

  it("velocity slider updates a note's velocity", () => {
    const note = makeNote(39, 0, 1);
    renderRoll([note]);
    fireEvent.change(screen.getByLabelText(`Velocity for note ${note.id}`), {
      target: { value: "64" },
    });
    const updated = onChange.mock.calls.at(-1)![0] as RollNote[];
    expect(updated[0].velocity).toBe(64);
  });
});
