import { useMemo, useState, useCallback } from "react";
import type { Sample } from "../types/api";

export interface ReviewFilterState {
  includeReviewed: boolean;
  reasonFilter: string;
  typeFilter: string;
  page: number;
  pageSize: number;
}

export interface ReviewFilterResult {
  allFlagged: Sample[];
  filtered: Sample[];
  pageRows: Sample[];
  totalPages: number;
  start: number;
  reviewedCount: number;
  pct: string;
  lowestConf: string;
  reasonCounts: [string, number][];
  typeCounts: [string, number][];
  hasFilters: boolean;
  state: ReviewFilterState;
  setIncludeReviewed: (v: boolean) => void;
  setReasonFilter: (v: string) => void;
  setTypeFilter: (v: string) => void;
  setPage: (v: number) => void;
  setPageSize: (v: number) => void;
  clearFilters: () => void;
}

export function useReviewFiltering(samples: Sample[]): ReviewFilterResult {
  const [includeReviewed, setIncludeReviewed] = useState(false);
  const [reasonFilter, setReasonFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);

  const allFlagged = useMemo(
    () => samples.filter((s) => s.needs_review),
    [samples],
  );

  const filtered = useMemo(() => {
    let list = allFlagged;
    if (!includeReviewed) {
      list = list.filter((s) => !s.reviewed);
    }
    if (reasonFilter) {
      list = list.filter((s) =>
        (s.review_reasons ?? []).includes(reasonFilter),
      );
    }
    if (typeFilter) {
      list = list.filter((s) => s.type === typeFilter);
    }
    return list.sort((a, b) => (a.confidence ?? 0) - (b.confidence ?? 0));
  }, [allFlagged, includeReviewed, reasonFilter, typeFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const start = (page - 1) * pageSize;
  const pageRows = filtered.slice(start, start + pageSize);

  const reviewedCount = useMemo(
    () => allFlagged.filter((s) => s.reviewed).length,
    [allFlagged],
  );

  const pct =
    samples.length > 0
      ? ((allFlagged.length / samples.length) * 100).toFixed(1)
      : "0";

  const lowestConf =
    filtered.length > 0 ? (filtered[0].confidence ?? 0).toFixed(2) : "—";

  const reasonCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of allFlagged) {
      for (const r of s.review_reasons ?? []) {
        counts.set(r, (counts.get(r) ?? 0) + 1);
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [allFlagged]);

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of allFlagged) {
      const t = s.type ?? "Unknown";
      counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [allFlagged]);

  const clearFilters = useCallback(() => {
    setReasonFilter("");
    setTypeFilter("");
    setPage(1);
  }, []);

  const hasFilters = reasonFilter !== "" || typeFilter !== "";

  return {
    allFlagged,
    filtered,
    pageRows,
    totalPages,
    start,
    reviewedCount,
    pct,
    lowestConf,
    reasonCounts,
    typeCounts,
    hasFilters,
    state: { includeReviewed, reasonFilter, typeFilter, page, pageSize },
    setIncludeReviewed: (v) => { setIncludeReviewed(v); setPage(1); },
    setReasonFilter: (v) => { setReasonFilter(v); setPage(1); },
    setTypeFilter: (v) => { setTypeFilter(v); setPage(1); },
    setPage,
    setPageSize: (v) => { setPageSize(v); setPage(1); },
    clearFilters,
  };
}
