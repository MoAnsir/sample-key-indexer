import { useMemo, memo, useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAppStore, applyFilters, sortSamples } from "../store/useAppStore";
import PaginationBar from "./PaginationBar";
import { getSampleField } from "../utils/sample";
import { keyColor, parseKey } from "../lib/key-color";
import { checkFit, fitLabel, type FitLevel } from "../lib/key-compat";
import { deleteSketch } from "../api/client";
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
      <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-accent-soft text-accent">
        Playable
      </span>
    );
  }
  if (status === "sketch") {
    return (
      <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-accent-soft text-accent">
        ✏ Sketch
      </span>
    );
  }
  return (
    <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-warn/15 text-warn">
      Missing
    </span>
  );
}

function KeyChip({ keyValue }: { keyValue: string | null }) {
  const isDark = useAppStore((s) => s.isDark);
  if (!keyValue) return <span className="text-faint text-xs">—</span>;
  const { root, mode } = parseKey(keyValue);
  const c = keyColor(root, mode, isDark);
  return (
    <span
      className="inline-block px-2 py-0.5 text-[11px] font-semibold rounded"
      style={{ background: c.bg, color: c.ink, border: `1px solid ${c.border}` }}
    >
      {keyValue.replace("_", " ")}
    </span>
  );
}

function ConfidenceMeter({ value }: { value: number | null }) {
  if (value == null) return <span className="text-faint text-xs">—</span>;
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 h-[5px] rounded-full bg-surface-2  overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: value >= 0.7 ? "#0d9488" : value >= 0.4 ? "#d97706" : "#dc2626",
          }}
        />
      </div>
      <span className="text-xs text-muted tabular-nums font-mono">{value.toFixed(2)}</span>
    </div>
  );
}

function FitBadge({ fit }: { fit: FitLevel }) {
  const styles: Record<FitLevel, string> = {
    same: "bg-good/15 text-good",
    compatible: "bg-accent-soft text-accent",
    out: "bg-warn/15 text-warn",
    none: "text-faint",
  };
  if (fit === "none") return <span className="text-xs text-faint">No key</span>;
  return (
    <span className={`inline-block px-2 py-0.5 text-[11px] font-medium rounded-full ${styles[fit]}`}>
      {fitLabel(fit)}
    </span>
  );
}

function SketchRowActions({ sample }: { sample: Sample }) {
  const queryClient = useQueryClient();
  const samples = useAppStore((s) => s.samples);
  const setSamples = useAppStore((s) => s.setSamples);

  const handleDelete = useCallback(
    async (event: React.MouseEvent) => {
      event.stopPropagation();
      if (!sample.sketch_id) return;
      if (!confirm(`Delete sketch "${sample.name}"?`)) return;
      try {
        await deleteSketch(sample.sketch_id);
        setSamples(samples.filter((s) => s.id !== sample.id));
        queryClient.invalidateQueries({ queryKey: ["catalog"] });
      } catch {
        // leave the row in place on failure
      }
    },
    [sample, samples, setSamples, queryClient],
  );

  return (
    <span className="inline-flex items-center gap-1.5 ml-1.5">
      <a
        href={`/api/sketch/midi?sketch_id=${sample.sketch_id}`}
        download
        onClick={(e) => e.stopPropagation()}
        className="text-[10px] text-accent hover:underline"
        title="Download this sketch as MIDI"
      >
        ⬇ MIDI
      </a>
      <button
        onClick={handleDelete}
        className="text-[10px] text-warn hover:underline"
        title="Delete this sketch"
      >
        ✕
      </button>
    </span>
  );
}

function CellValue({ sample, column }: { sample: Sample; column: string }) {
  const value = getSampleField(sample, column);

  if (column === "playback_status") {
    const isSketch = sample.source_kind === "sketch" && sample.sketch_id;
    return (
      <>
        <StatusBadge status={String(value ?? "missing")} />
        {isSketch && <SketchRowActions sample={sample} />}
      </>
    );
  }
  if (column === "key") {
    return <KeyChip keyValue={value as string | null} />;
  }
  if (column === "duration") {
    return <>{formatDuration(value as number | null)}</>;
  }
  if (column === "bpm") {
    return <>{value != null ? `${Math.round(value as number)} BPM` : "—"}</>;
  }
  if (column === "confidence") {
    return <ConfidenceMeter value={value as number | null} />;
  }
  if (value == null || value === "") return <>—</>;
  return <>{String(value)}</>;
}

const SampleRow = memo(function SampleRow({
  sample,
  isSelected,
  isHighlighted,
  projectKey,
  onClick,
}: {
  sample: Sample;
  isSelected: boolean;
  isHighlighted: boolean;
  projectKey: string | null;
  onClick: () => void;
}) {
  const fit = checkFit(sample.key, projectKey);
  return (
    <tr
      className={`hover:bg-accent-soft cursor-pointer transition-colors ${
        isSelected ? "bg-accent-soft" : isHighlighted ? "bg-surface-2" : ""
      }`}
      onClick={onClick}
    >
      {COLUMNS.map((col) => (
        <td
          key={col.key}
          className={`px-3 py-2 text-ink whitespace-nowrap ${col.className ?? ""}`}
        >
          <CellValue sample={sample} column={col.key} />
        </td>
      ))}
      {projectKey && (
        <td className="px-3 py-2 whitespace-nowrap">
          <FitBadge fit={fit} />
        </td>
      )}
    </tr>
  );
});

export default function SampleTable() {
  const samples = useAppStore((s) => s.samples);
  const filters = useAppStore((s) => s.filters);
  const projectKey = useAppStore((s) => s.projectKey);
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
          <thead className="sticky top-0 bg-surface-2 z-10">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 text-left text-xs font-medium text-muted uppercase tracking-wider cursor-pointer select-none hover:text-ink whitespace-nowrap ${col.className ?? ""}`}
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
              {projectKey && (
                <th className="px-3 py-2 text-left text-xs font-medium text-muted uppercase tracking-wider whitespace-nowrap">
                  Fit
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {pageRows.map((sample, i) => (
              <SampleRow
                key={sample.id}
                sample={sample}
                isSelected={selectedSampleId === sample.id}
                isHighlighted={highlightedIndex === i}
                projectKey={projectKey}
                onClick={() => handleRowClick(sample.id)}
              />
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td
                  colSpan={COLUMNS.length + (projectKey ? 1 : 0)}
                  className="px-4 py-12 text-center text-faint"
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
