import { describe, it, expect, beforeEach } from "vitest";
import { applyFilters, sortSamples } from "./useAppStore";
import { MOCK_SAMPLES } from "../test/mocks/handlers";
import type { FilterState } from "./useAppStore";

const blank: FilterState = {
  search: "",
  libraryId: "",
  playback: "",
  category: "",
  type: "",
  key: "",
  source: "",
  brightness: "",
  warmth: "",
  bpmMin: "",
  bpmMax: "",
  confidence: 0,
  unsortedOnly: false,
};

describe("applyFilters", () => {
  it("returns all samples when no filters active", () => {
    expect(applyFilters(MOCK_SAMPLES, blank)).toHaveLength(3);
  });

  it("filters by search term (name match)", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, search: "bass" });
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("Bass");
  });

  it("filters by search term (key match)", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, search: "E_minor" });
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(3);
  });

  it("filters by playback status", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, playback: "missing" });
    expect(result).toHaveLength(1);
    expect(result[0].playback_status).toBe("missing");
  });

  it("filters by category", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, category: "Loops" });
    expect(result).toHaveLength(2);
  });

  it("filters by type", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, type: "Kick" });
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("Kick");
  });

  it("filters by key", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, key: "A_minor" });
    expect(result).toHaveLength(1);
    expect(result[0].root_note).toBe("A");
  });

  it("filters by root_note when key filter set to a note", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, key: "C" });
    // root_note match
    expect(result).toHaveLength(1);
    expect(result[0].root_note).toBe("C");
  });

  it("filters by min BPM", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, bpmMin: "100" });
    expect(result).toHaveLength(1);
    expect(result[0].bpm).toBe(120);
  });

  it("filters by max BPM", () => {
    // samples: bpm 120 (kick), 90 (bass), 0 (pad) — bpmMax:95 keeps 90 and 0
    const result = applyFilters(MOCK_SAMPLES, { ...blank, bpmMax: "95" });
    expect(result).toHaveLength(2);
    expect(result.every((s) => (s.bpm ?? 0) <= 95)).toBe(true);
  });

  it("filters by min confidence", () => {
    const result = applyFilters(MOCK_SAMPLES, { ...blank, confidence: 0.9 });
    expect(result).toHaveLength(1);
    expect(result[0].confidence).toBeGreaterThanOrEqual(0.9);
  });

  it("multiple filters compose (AND logic)", () => {
    const result = applyFilters(MOCK_SAMPLES, {
      ...blank,
      category: "Loops",
      playback: "available",
    });
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(2);
  });
});

describe("sortSamples", () => {
  it("sorts by name ascending", () => {
    const sorted = sortSamples(MOCK_SAMPLES, "name", "asc");
    const names = sorted.map((s) => s.name);
    expect(names).toEqual([...names].sort());
  });

  it("sorts by name descending", () => {
    const sorted = sortSamples(MOCK_SAMPLES, "name", "desc");
    const names = sorted.map((s) => s.name);
    expect(names).toEqual([...names].sort().reverse());
  });

  it("sorts by bpm numerically", () => {
    const sorted = sortSamples(MOCK_SAMPLES, "bpm", "asc");
    const bpms = sorted.map((s) => s.bpm ?? 0);
    expect(bpms[0]).toBeLessThanOrEqual(bpms[1]);
    expect(bpms[1]).toBeLessThanOrEqual(bpms[2]);
  });

  it("sorts by confidence descending", () => {
    const sorted = sortSamples(MOCK_SAMPLES, "confidence", "desc");
    const confs = sorted.map((s) => s.confidence ?? 0);
    expect(confs[0]).toBeGreaterThanOrEqual(confs[1]);
  });

  it("puts null values last", () => {
    const samplesWithNull = [
      { ...MOCK_SAMPLES[0], confidence: null as unknown as number },
      ...MOCK_SAMPLES.slice(1),
    ];
    const sorted = sortSamples(samplesWithNull, "confidence", "asc");
    expect(sorted[sorted.length - 1].confidence).toBeNull();
  });
});
