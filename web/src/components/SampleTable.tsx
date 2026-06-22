import { useMemo } from "react";
import { useAppStore, applyFilters, sortSamples } from "../store/useAppStore";
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

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Pagination header */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200">
        <div className="text-sm text-gray-600">
          <span className="font-medium">
            {filtered.length.toLocaleString()}
          </span>{" "}
          of {samples.length.toLocaleString()} matching samples
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-gray-500">
            Rows
            <select
              className="ml-1.5 input-base"
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
            >
              {[100, 250, 500, 1000].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            className="text-sm text-gray-500 hover:text-gray-800 disabled:opacity-30"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            className="text-sm text-gray-500 hover:text-gray-800 disabled:opacity-30"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 bg-gray-50 z-10">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer select-none hover:text-gray-800 whitespace-nowrap ${col.className ?? ""}`}
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
          <tbody className="divide-y divide-gray-100">
            {pageRows.map((sample) => (
              <tr
                key={sample.id}
                className={`hover:bg-teal-50 cursor-pointer transition-colors ${
                  selectedSampleId === sample.id ? "bg-teal-100" : ""
                }`}
                onClick={() => setSelectedSampleId(sample.id)}
              >
                {COLUMNS.map((col) => (
                  <td
                    key={col.key}
                    className={`px-3 py-2 text-gray-700 whitespace-nowrap ${col.className ?? ""}`}
                  >
                    <CellValue sample={sample} column={col.key} />
                  </td>
                ))}
              </tr>
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
    </div>
  );
}
