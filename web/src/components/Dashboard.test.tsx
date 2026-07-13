import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Dashboard from "./Dashboard";
import { MOCK_CATALOG } from "../test/mocks/handlers";
import * as client from "../api/client";

// stub zustand store — Dashboard reads samples for KeyDistribution
vi.mock("../store/useAppStore", () => ({
  useAppStore: () => [],
}));

const onLibrarySelect = vi.fn();
const onRefresh = vi.fn();

function renderDashboard(overrides = {}) {
  return render(
    <Dashboard
      catalog={MOCK_CATALOG}
      activeLibraryId=""
      onLibrarySelect={onLibrarySelect}
      onRefresh={onRefresh}
      {...overrides}
    />,
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    onLibrarySelect.mockReset();
    onRefresh.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a card for each library", () => {
    renderDashboard();
    expect(screen.getByText("Pack A")).toBeInTheDocument();
    expect(screen.getByText("Pack B")).toBeInTheDocument();
  });

  it("shows sample counts", () => {
    renderDashboard();
    expect(screen.getByText("2 samples")).toBeInTheDocument();
    expect(screen.getByText("1 samples")).toBeInTheDocument();
  });

  it("highlights the active library card", () => {
    renderDashboard({ activeLibraryId: "lib_1" });
    const cards = document.querySelectorAll(".ring-accent");
    expect(cards).toHaveLength(1);
  });

  it("calls onLibrarySelect when card content clicked", () => {
    renderDashboard();
    fireEvent.click(screen.getByText("Pack A"));
    expect(onLibrarySelect).toHaveBeenCalledWith("lib_1");
  });

  it("shows Remove library button when indexPath present", () => {
    renderDashboard();
    const deleteButtons = screen.getAllByText("Remove library & delete scan data");
    expect(deleteButtons).toHaveLength(2);
  });

  it("calls deleteScanData and reloadIndex then onRefresh on confirmed delete", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const deleteSpy = vi.spyOn(client, "deleteScanData").mockResolvedValue({ deleted: [], errors: [] });
    const reloadSpy = vi.spyOn(client, "reloadIndex").mockResolvedValue(undefined);

    renderDashboard();
    fireEvent.click(screen.getAllByText("Remove library & delete scan data")[0]);

    // indexPath is "/data/lib_1.sqlite" — regex only strips "/metadata_index.sqlite" suffix
    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("/data/lib_1.sqlite"));
    await waitFor(() => expect(reloadSpy).toHaveBeenCalled());
    await waitFor(() => expect(onRefresh).toHaveBeenCalled());
  });

  it("does not delete if user cancels confirm", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const deleteSpy = vi.spyOn(client, "deleteScanData").mockResolvedValue({ deleted: [], errors: [] });

    renderDashboard();
    fireEvent.click(screen.getAllByText("Remove library & delete scan data")[0]);

    expect(deleteSpy).not.toHaveBeenCalled();
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("shows stats section by default and toggles it", () => {
    renderDashboard();
    expect(screen.getByText("Sample Types")).toBeInTheDocument();
    fireEvent.click(screen.getByText("▲ Hide charts"));
    expect(screen.queryByText("Sample Types")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("▼ Show charts"));
    expect(screen.getByText("Sample Types")).toBeInTheDocument();
  });
});
