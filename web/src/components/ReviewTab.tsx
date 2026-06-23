import { useMemo, useState, useCallback } from "react";
import { useAppStore } from "../store/useAppStore";
import PaginationBar from "./PaginationBar";
import type { Sample } from "../types/api";

export default function ReviewTab() {
  const samples = useAppStore((s) => s.samples);
  const setSelectedSampleId = useAppStore((s) => s.setSelectedSampleId);
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

  const reviewedCount = allFlagged.filter((s) => s.reviewed).length;
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

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Summary + filters */}
      <div className="p-4 space-y-4 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <StatCard label="Flagged" value={allFlagged.length.toLocaleString()} />
          <StatCard label="% of library" value={`${pct}%`} />
          <StatCard label="Reviewed" value={`${reviewedCount} / ${allFlagged.length}`} />
          <StatCard label="Remaining" value={(allFlagged.length - reviewedCount).toLocaleString()} />
          <StatCard label="Lowest confidence" value={lowestConf} />
        </div>

        {/* Reason breakdown — clickable to filter */}
        {reasonCounts.length > 0 && (
          <div>
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1.5">
              Filter by reason
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {reasonCounts.map(([reason, count]) => (
                <button
                  key={reason}
                  onClick={() => {
                    setReasonFilter(reasonFilter === reason ? "" : reason);
                    setPage(1);
                  }}
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                    reasonFilter === reason
                      ? "bg-teal-600 text-white"
                      : "border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:border-teal-400"
                  }`}
                >
                  <span className="font-mono">{reason}</span>
                  <span className="font-semibold">{count}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Type breakdown — clickable to filter */}
        {typeCounts.length > 0 && (
          <div>
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1.5">
              Filter by type
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {typeCounts.map(([type, count]) => (
                <button
                  key={type}
                  onClick={() => {
                    setTypeFilter(typeFilter === type ? "" : type);
                    setPage(1);
                  }}
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                    typeFilter === type
                      ? "bg-teal-600 text-white"
                      : "border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:border-teal-400"
                  }`}
                >
                  {type}
                  <span className="font-semibold">{count}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Controls row */}
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={includeReviewed}
              onChange={(e) => {
                setIncludeReviewed(e.target.checked);
                setPage(1);
              }}
            />
            Include reviewed
          </label>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-teal-700 hover:text-teal-900 underline"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Pagination top */}
      <PaginationBar
        position="top"
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        showingFrom={filtered.length > 0 ? start + 1 : 0}
        showingTo={Math.min(start + pageSize, filtered.length)}
        totalFiltered={filtered.length}
        totalAll={allFlagged.length}
        label="flagged samples"
        onPageChange={setPage}
        onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
      />

      {/* Review list */}
      <div className="flex-1 overflow-auto">
        {pageRows.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            No samples match the current filters
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {pageRows.map((sample) => (
              <ReviewRow
                key={sample.id}
                sample={sample}
                onClick={() => setSelectedSampleId(sample.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pagination bottom */}
      <PaginationBar
        position="bottom"
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        showingFrom={filtered.length > 0 ? start + 1 : 0}
        showingTo={Math.min(start + pageSize, filtered.length)}
        totalFiltered={filtered.length}
        totalAll={allFlagged.length}
        label="flagged samples"
        onPageChange={setPage}
        onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
      />
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-2.5">
      <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
        {label}
      </p>
      <p className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-0.5">{value}</p>
    </div>
  );
}

function ReviewRow({
  sample,
  onClick,
}: {
  sample: Sample;
  onClick: () => void;
}) {
  const reasons = sample.review_reasons ?? [];

  return (
    <button
      onClick={onClick}
      className="w-full flex items-start gap-3 px-4 py-3 hover:bg-teal-50 dark:hover:bg-teal-950 text-left transition-colors"
    >
      {/* Confidence */}
      <span
        className={`w-10 text-xs font-mono font-bold tabular-nums shrink-0 mt-0.5 ${
          (sample.confidence ?? 0) < 0.3
            ? "text-red-600"
            : (sample.confidence ?? 0) < 0.6
              ? "text-amber-600"
              : "text-gray-600 dark:text-gray-400"
        }`}
      >
        {(sample.confidence ?? 0).toFixed(2)}
      </span>

      {/* Name + reasons */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
          {sample.name}
        </p>
        {reasons.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {reasons.map((r) => (
              <span
                key={r}
                className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-50 text-amber-700 border border-amber-200"
              >
                {r}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Meta */}
      <div className="flex items-center gap-2 shrink-0 mt-0.5">
        <span className="text-xs text-gray-400">{sample.type}</span>
        <span className="text-xs text-gray-400">{sample.key ?? "—"}</span>
        {sample.reviewed && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-teal-100 text-teal-700">
            Reviewed
          </span>
        )}
      </div>
    </button>
  );
}
