import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SketchResults from "./SketchResults";
import { MOCK_SKETCH_ANALYSIS } from "../test/mocks/handlers";
import type { SketchAnalysis } from "../api/client";

const onDownloadMidi = vi.fn();
const analysis = MOCK_SKETCH_ANALYSIS as unknown as SketchAnalysis;

function renderResults(overrides: Partial<Parameters<typeof SketchResults>[0]> = {}) {
  return render(
    <SketchResults
      analysis={analysis}
      hasNotes={false}
      onDownloadMidi={onDownloadMidi}
      midiBusy={false}
      {...overrides}
    />,
  );
}

beforeEach(() => {
  onDownloadMidi.mockReset();
});

describe("SketchResults", () => {
  it("shows summary chips", () => {
    renderResults();
    expect(screen.getByText("D#_minor")).toBeInTheDocument();
    expect(screen.getAllByText("dark").length).toBeGreaterThan(0);
    expect(screen.getByText("140")).toBeInTheDocument();
    expect(screen.getAllByText("D# minor").length).toBeGreaterThan(0);
  });

  it("labels notes as scale notes without user notes", () => {
    renderResults();
    expect(screen.getByText("Scale notes")).toBeInTheDocument();
  });

  it("labels notes as played when user entered notes", () => {
    renderResults({ hasNotes: true });
    expect(screen.getByText("Notes you played")).toBeInTheDocument();
  });

  it("hides MIDI download without notes", () => {
    renderResults();
    expect(screen.queryByText(/download your notes as midi/i)).not.toBeInTheDocument();
  });

  it("shows MIDI download with notes and triggers callback", () => {
    renderResults({ hasNotes: true });
    const button = screen.getByText(/download your notes as midi/i);
    fireEvent.click(button);
    expect(onDownloadMidi).toHaveBeenCalled();
  });

  it("disables MIDI button while busy", () => {
    renderResults({ hasNotes: true, midiBusy: true });
    expect(screen.getByText(/generating midi/i)).toBeDisabled();
  });

  it("renders all compatible keys with chords", () => {
    renderResults();
    expect(screen.getByText("Same key")).toBeInTheDocument();
    expect(screen.getByText("Relative key")).toBeInTheDocument();
    expect(screen.getByText("F# major")).toBeInTheDocument();
  });

  it("renders progressions with mood badge and roman numerals", () => {
    renderResults();
    expect(screen.getByText("Minor lift")).toBeInTheDocument();
    expect(screen.getByText("D#m – B – F#")).toBeInTheDocument();
    expect(screen.getByText(/\(i – VI – III\)/)).toBeInTheDocument();
  });

  it("renders mood profile and transition suggestions", () => {
    renderResults();
    expect(screen.getByText(/primary mood/i)).toBeInTheDocument();
    expect(
      screen.getByText(/dark material usually moves well into driving textures/i),
    ).toBeInTheDocument();
  });

  it("shows out-of-scale warning when present", () => {
    renderResults({
      analysis: { ...analysis, out_of_scale_notes: ["E"] } as SketchAnalysis,
    });
    expect(screen.getByText(/out-of-scale notes: e/i)).toBeInTheDocument();
  });

  it("hides out-of-scale warning when empty", () => {
    renderResults();
    expect(screen.queryByText(/out-of-scale/i)).not.toBeInTheDocument();
  });
});
