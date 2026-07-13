import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import SketchWizard from "./SketchWizard";
import { server } from "../test/mocks/server";
import * as client from "../api/client";

const onClose = vi.fn();
const onSaved = vi.fn();

function renderWizard() {
  return render(<SketchWizard onClose={onClose} onSaved={onSaved} />);
}

describe("SketchWizard — details form", () => {
  beforeEach(() => {
    onClose.mockReset();
    onSaved.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders all form fields", () => {
    renderWizard();
    expect(screen.getByText("New Sketch")).toBeInTheDocument();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/bpm/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/bars/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/beats \/ bar/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/frequency register/i)).toBeInTheDocument();
  });

  it("shows flat/sharp key labels like the MPC", () => {
    renderWizard();
    expect(screen.getByRole("option", { name: "D# / Eb" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "A# / Bb" })).toBeInTheDocument();
  });

  it("defaults to minor scale", () => {
    renderWizard();
    const minorButton = screen.getByText("Minor");
    expect(minorButton.className).toContain("bg-surface ");
    const majorButton = screen.getByText("Major");
    expect(majorButton.className).not.toContain("bg-surface ");
  });

  it("disables Analyze when BPM is out of range", () => {
    renderWizard();
    fireEvent.change(screen.getByLabelText(/bpm/i), { target: { value: "1000" } });
    expect(screen.getByRole("button", { name: /analyze/i })).toBeDisabled();
  });

  it("disables Analyze when bars is out of range", () => {
    renderWizard();
    fireEvent.change(screen.getByLabelText(/bars/i), { target: { value: "0" } });
    expect(screen.getByRole("button", { name: /analyze/i })).toBeDisabled();
  });

  it("calls onClose from Cancel", () => {
    renderWizard();
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("sends the form values to analyzeSketch", async () => {
    const spy = vi.spyOn(client, "analyzeSketch");
    renderWizard();
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "MPC bass idea" } });
    fireEvent.change(screen.getByLabelText(/key/i), { target: { value: "D#" } });
    fireEvent.change(screen.getByLabelText(/bpm/i), { target: { value: "140" } });
    fireEvent.change(screen.getByLabelText(/type/i), { target: { value: "Bass" } });
    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));

    await waitFor(() => expect(spy).toHaveBeenCalled());
    const payload = spy.mock.calls[0][0];
    expect(payload.name).toBe("MPC bass idea");
    expect(payload.tonic).toBe("D#");
    expect(payload.mode).toBe("minor");
    expect(payload.bpm).toBe(140);
    expect(payload.bars).toBe(8);
    expect(payload.type).toBe("Bass");
  });
});

describe("SketchWizard — results step", () => {
  beforeEach(() => {
    onClose.mockReset();
    onSaved.mockReset();
  });

  async function analyzeToResults() {
    renderWizard();
    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));
    await waitFor(() => expect(screen.getByText("Sketch Analysis")).toBeInTheDocument());
  }

  it("shows key, mood and compatible keys after analysis", async () => {
    await analyzeToResults();
    expect(screen.getByText("D#_minor")).toBeInTheDocument();
    expect(screen.getAllByText("dark").length).toBeGreaterThan(0);
    expect(screen.getByText(/relative key/i)).toBeInTheDocument();
    expect(screen.getAllByText("F# major").length).toBeGreaterThan(0);
  });

  it("saves the sketch and notifies parent", async () => {
    await analyzeToResults();
    fireEvent.click(screen.getByRole("button", { name: /save sketch/i }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(screen.getByText(/sketch saved/i)).toBeInTheDocument();
    // Save button replaced by Done
    expect(screen.getByRole("button", { name: /done/i })).toBeInTheDocument();
  });

  it("Back returns to the details form", async () => {
    await analyzeToResults();
    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(screen.getByText("New Sketch")).toBeInTheDocument();
  });

  it("shows API errors from analyze", async () => {
    server.use(
      http.post("/api/sketch/analyze", () =>
        HttpResponse.json({ ok: false, errors: ["bpm must be between 20 and 400"] }, { status: 400 }),
      ),
    );
    renderWizard();
    fireEvent.click(screen.getByRole("button", { name: /analyze/i }));
    await waitFor(() =>
      expect(screen.getByText(/bpm must be between 20 and 400/i)).toBeInTheDocument(),
    );
  });

  it("shows out-of-scale warning when present", async () => {
    const { MOCK_SKETCH_ANALYSIS } = await import("../test/mocks/handlers");
    server.use(
      http.post("/api/sketch/analyze", () =>
        HttpResponse.json({ ...MOCK_SKETCH_ANALYSIS, out_of_scale_notes: ["E"] }),
      ),
    );
    await analyzeToResults();
    expect(screen.getByText(/out-of-scale notes: e/i)).toBeInTheDocument();
  });
});
