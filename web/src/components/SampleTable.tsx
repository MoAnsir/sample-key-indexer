import { useMemo, memo, useCallback, useEffect, useRef, useState } from "react";
import { useAppStore, applyFilters, sortSamples } from "../store/useAppStore";
import PaginationBar from "./PaginationBar";
import type { Sample } from "../types/api";

const COLUMNS: { key: string; label: string; className?: string }[] = [
  { key: "name", label: "Name", className: "min-w-[200px]" },
  { key: "library_name", label: "Library" },
  { key: "playback_status", label: "Status" },
  { key: "key", label: "Key" },
  { key: "category", label: "Category" },
  { key: "type", label: "Type" },
  { key: "subtype", label: "Subtype" },
  { key: "source", label: "Source" },
  { key: "brightness", label: "Brightness" },
  { key: "warmth", label: "Warmth" },
  { key: "duration", label: "Duration" },
  { key: "bpm", label: "BPM" },
  { key: "confidence", label: "Confidence" },
];

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "available") {
    return (
      <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-teal-100 text-teal-800">
        Playable
      </span>
    );
  }
  return (
    <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-800">
      Missing
    </span>
  );
}

function CellValue({ sample, column }: { sample: Sample; column: string }) {
  const value = (sample as unknown as Record<string, unknown>)[column];

  if (column === "playback_status") {
    return <StatusBadge status={String(value ?? "missing")} />;
  }
  if (column === "duration") {
    return <>{formatDuration(value as number | null)}</>;
  }
  if (column === "bpm") {
    return <>{value != null ? `${Math.round(value as number)} BPM` : "—"}</>;
  }
  if (column === "confidence") {
    return <>{value != null ? (value as number).toFixed(2) : "—"}</>;
  }
  if (value == null || value === "") return <>—</>;
  return <>{String(value)}</>;
}

const SampleRow = memo(function SampleRow({
  sample,
  isSelected,
  isHighlighted,
  onClick,
}: {
  sample: Sample;
  isSelected: boolean;
  isHighlighted: boolean;
  onClick: () => void;
}) {
  return (
    <tr
      className={`hover:bg-teal-50 dark:hover:bg-teal-950 cursor-pointer transition-colors ${
        isSelected ? "bg-teal-100 dark:bg-teal-900" : isHighlighted ? "bg-gray-100 dark:bg-gray-800" : ""
      }`}
      onClick={onClick}
    >
      {COLUMNS.map((col) => (
        <td
          key={col.key}
          className={`px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap ${col.className ?? ""}`}
        >
          <CellValue sample={sample} column={col.key} />
        </td>
      ))}
    </tr>
  );
});

export default function SampleTable() {
  const samples = useAppStore((s) => s.samples);
  const filters = useAppStore((s) => s.filters);
  const sortKey = useAppStore((s) => s.sortKey);
  const sortDirection = useAppStore((s) => s.sortDirection);
  const setSort = useAppStore((s) => s.setSort);
  const page = useAppStore((s) => s.page);
  const pageSize = useAppStore((s) => s.pageSize);
  const setPage = useAppStore((s) => s.setPage);
  const setPageSize = useAppStore((s) => s.setPageSize);
  const selectedSampleId = useAppStore((s) => s.selectedSampleId);
  const setSelectedSampleId = useAppStore((s) => s.setSelectedSampleId);

  const filtered = useMemo(
    () => sortSamples(applyFilters(samples, filters), sortKey, sortDirection),
    [samples, filters, sortKey, sortDirection],
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const start = (page - 1) * pageSize;
  const pageRows = filtered.slice(start, start + pageSize);

  const tableRef = useRef<HTMLDivElement>(null);

  const handleRowClick = useCallback(
    (id: number) => setSelectedSampleId(id),
    [setSelectedSampleId],
  );

  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  // Keyboard navigation — arrow keys highlight, Enter opens detail
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      // Don't intercept when detail panel is open
      if (useAppStore.getState().selectedSampleId != null) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((prev) => Math.min(prev + 1, pageRows.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && highlightedIndex >= 0 && pageRows[highlightedIndex]) {
        e.preventDefault();
        setSelectedSampleId(pageRows[highlightedIndex].id);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [pageRows, highlightedIndex, setSelectedSampleId]);

  // Scroll highlighted row into view
  useEffect(() => {
    if (highlightedIndex >= 0) {
      const row = tableRef.current?.querySelectorAll("tbody tr")[highlightedIndex];
      row?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightedIndex]);

  // Reset highlight when page changes
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [page, pageSize]);

  const showingFrom = filtered.length > 0 ? start + 1 : 0;
  const showingTo = Math.min(start + pageSize, filtered.length);

  const paginationProps = {
    page,
    totalPages,
    pageSize,
    showingFrom,
    showingTo,
    totalFiltered: filtered.length,
    totalAll: samples.length,
    onPageChange: setPage,
    onPageSizeChange: setPageSize,
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <PaginationBar position="top" {...paginationProps} />

      {/* Table */}
      <div ref={tableRef} className="flex-1 overflow-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800 z-10">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200 whitespace-nowrap ${col.className ?? ""}`}
                  onClick={() => setSort(col.key)}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-1">
                      {sortDirection === "asc" ? "↑" : "↓"}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {pageRows.map((sample, i) => (
              <SampleRow
                key={sample.id}
                sample={sample}
                isSelected={selectedSampleId === sample.id}
                isHighlighted={highlightedIndex === i}
                onClick={() => handleRowClick(sample.id)}
              />
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td
                  colSpan={COLUMNS.length}
                  className="px-4 py-12 text-center text-gray-400"
                >
                  No samples match your filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <PaginationBar position="bottom" {...paginationProps} />
    </div>
  );
}
