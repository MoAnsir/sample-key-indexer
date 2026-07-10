import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useReviewFiltering } from "./useReviewFiltering";
import { MOCK_SAMPLES } from "../test/mocks/handlers";

describe("useReviewFiltering", () => {
  it("returns only flagged samples", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    expect(result.current.allFlagged).toHaveLength(2);
    expect(result.current.allFlagged.every((s) => s.needs_review)).toBe(true);
  });

  it("excludes reviewed samples by default", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    // sample id=3 is reviewed — should be excluded from filtered
    expect(result.current.filtered.every((s) => !s.reviewed)).toBe(true);
    expect(result.current.filtered).toHaveLength(1);
  });

  it("includes reviewed when includeReviewed toggled on", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    act(() => result.current.setIncludeReviewed(true));
    expect(result.current.filtered).toHaveLength(2);
  });

  it("filters by reason", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    act(() => {
      result.current.setIncludeReviewed(true);
      result.current.setReasonFilter("filename_key_disagreement");
    });
    expect(result.current.filtered).toHaveLength(1);
    expect(result.current.filtered[0].id).toBe(3);
  });

  it("filters by type", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    act(() => {
      result.current.setIncludeReviewed(true);
      result.current.setTypeFilter("Bass");
    });
    expect(result.current.filtered).toHaveLength(1);
    expect(result.current.filtered[0].type).toBe("Bass");
  });

  it("sorts filtered results by ascending confidence", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    act(() => result.current.setIncludeReviewed(true));
    const confs = result.current.filtered.map((s) => s.confidence ?? 0);
    expect(confs).toEqual([...confs].sort((a, b) => a - b));
  });

  it("computes pct relative to total samples", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    // 2 of 3 samples need review → 66.7%
    expect(result.current.pct).toBe("66.7");
  });

  it("computes reviewedCount correctly", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    expect(result.current.reviewedCount).toBe(1);
  });

  it("counts reasons across all flagged samples", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    const counts = Object.fromEntries(result.current.reasonCounts);
    expect(counts["low_confidence"]).toBe(1);
    expect(counts["engine_key_disagreement"]).toBe(1);
    expect(counts["filename_key_disagreement"]).toBe(1);
  });

  it("resets page to 1 when filter changes", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    act(() => result.current.setPage(3));
    expect(result.current.state.page).toBe(3);
    act(() => result.current.setReasonFilter("low_confidence"));
    expect(result.current.state.page).toBe(1);
  });

  it("clearFilters removes reason and type filters", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    act(() => {
      result.current.setReasonFilter("low_confidence");
      result.current.setTypeFilter("Bass");
    });
    expect(result.current.hasFilters).toBe(true);
    act(() => result.current.clearFilters());
    expect(result.current.hasFilters).toBe(false);
  });

  it("paginates correctly", () => {
    const { result } = renderHook(() => useReviewFiltering(MOCK_SAMPLES));
    act(() => {
      result.current.setIncludeReviewed(true);
      result.current.setPageSize(1);
    });
    expect(result.current.totalPages).toBe(2);
    expect(result.current.pageRows).toHaveLength(1);
    act(() => result.current.setPage(2));
    expect(result.current.pageRows[0].id).toBe(3);
  });
});
