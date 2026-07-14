import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SampleTable from "./SampleTable";
import { useAppStore } from "../store/useAppStore";
import { MOCK_SAMPLES } from "../test/mocks/handlers";
import * as client from "../api/client";
import type { Sample } from "../types/api";

const SKETCH_SAMPLE = {
  id: 99,
  name: "MPC bass idea",
  file_path: "sketch://abc123",
  key: "D#_minor",
  root_note: "D#",
  type: "Bass",
  category: "OneShots",
  bpm: 140,
  confidence: 1.0,
  needs_review: false,
  reviewed: false,
  review_reasons: [],
  library_id: "sketches",
  library_name: "Sketches",
  playback_status: "sketch",
  source_kind: "sketch",
  sketch_id: "abc123",
  duration: 13.7,
} as unknown as Sample;

function renderTable(samples: Sample[]) {
  useAppStore.setState({ samples, page: 1 });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <SampleTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  useAppStore.getState().resetFilters();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SampleTable — sketch rows", () => {
  it("shows the sketch status badge instead of Missing", () => {
    renderTable([SKETCH_SAMPLE]);
    expect(screen.getByText("✏ Sketch")).toBeInTheDocument();
    expect(screen.queryByText("Missing")).not.toBeInTheDocument();
  });

  it("regular missing samples still show Missing", () => {
    renderTable([{ ...MOCK_SAMPLES[2] }]);
    expect(screen.getByText("Missing")).toBeInTheDocument();
  });

  it("renders a MIDI download link pointing at the sketch endpoint", () => {
    renderTable([SKETCH_SAMPLE]);
    const link = screen.getByText("⬇ MIDI");
    expect(link).toHaveAttribute("href", "/api/sketch/midi?sketch_id=abc123");
    expect(link).toHaveAttribute("download");
  });

  it("does not render sketch actions for regular samples", () => {
    renderTable([{ ...MOCK_SAMPLES[0] }]);
    expect(screen.queryByText("⬇ MIDI")).not.toBeInTheDocument();
  });

  it("delete asks for confirmation and removes the row", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const deleteSpy = vi.spyOn(client, "deleteSketch").mockResolvedValue(undefined);
    renderTable([SKETCH_SAMPLE]);
    fireEvent.click(screen.getByTitle("Delete this sketch"));
    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("abc123"));
    await waitFor(() =>
      expect(screen.queryByText("MPC bass idea")).not.toBeInTheDocument(),
    );
  });

  it("cancelled confirm leaves the sketch alone", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const deleteSpy = vi.spyOn(client, "deleteSketch").mockResolvedValue(undefined);
    renderTable([SKETCH_SAMPLE]);
    fireEvent.click(screen.getByTitle("Delete this sketch"));
    expect(deleteSpy).not.toHaveBeenCalled();
    expect(screen.getByText("MPC bass idea")).toBeInTheDocument();
  });
});
