import { useState, useCallback } from "react";
import type { CatalogResponse } from "../types/api";
import TypePieChart from "./TypePieChart";
import KeyDistribution from "./KeyDistribution";
import { useAppStore } from "../store/useAppStore";
import { deleteScanData, reloadIndex } from "../api/client";

interface DashboardProps {
  catalog: CatalogResponse;
  activeLibraryId: string;
  onLibrarySelect: (libraryId: string) => void;
  onRefresh: () => void;
}

export default function Dashboard({ catalog, activeLibraryId, onLibrarySelect, onRefresh }: DashboardProps) {
  const [collapsed, setCollapsed] = useState(false);
  const samples = useAppStore((s) => s.samples);
  const libraries = catalog.libraries ?? [];
  const stats = catalog.stats ?? [];

  const handleDeleteLibrary = useCallback(async (indexPath: string) => {
    const outputDir = indexPath.replace(/\/metadata_index\.(sqlite|json)$/, "");
    if (!confirm(`Delete scan data from:\n${outputDir}\n\nThis removes the index files and organized folders (Key/, Unsorted/).\nYour original source audio files are NOT affected.`)) {
      return;
    }
    try {
      await deleteScanData(outputDir);
      await reloadIndex();
      onRefresh();
    } catch {
      // ignore
    }
  }, [onRefresh]);

  return (
    <div className="border-b border-line bg-surface">
      <div className="px-6 py-3 space-y-3">
        {/* Library cards — always visible */}
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {libraries.length} {libraries.length === 1 ? "library" : "libraries"} loaded
          </h2>
          {stats.length > 0 && (
            <button
              onClick={() => setCollapsed((c) => !c)}
              className="text-xs text-muted hover:text-ink transition-colors"
            >
              {collapsed ? "▼ Show charts" : "▲ Hide charts"}
            </button>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {libraries.map((lib) => {
            const isActive = lib.id === activeLibraryId;
            const indexPath = lib.index_paths?.[0] ?? "";
            return (
              <div
                key={lib.id}
                className={`rounded-lg border p-3 text-left transition-all ${
                  isActive
                    ? "border-accent bg-accent-soft shadow-md ring-1 ring-accent"
                    : "border-line bg-surface shadow-sm hover:border-accent hover:shadow-md"
                }`}
              >
                <div
                  className="cursor-pointer"
                  onClick={() => onLibrarySelect(lib.id)}
                >
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink">
                    {lib.name}
                  </h3>
                  <p className="mt-0.5 text-base font-medium text-ink">
                    {(lib.total ?? 0).toLocaleString()} samples
                  </p>
                  <div className="mt-1 flex gap-3 text-xs text-muted">
                    <span>{(lib.available ?? 0).toLocaleString()} available</span>
                    {(lib.missing ?? 0) > 0 && (
                      <span className="text-warn">
                        {lib.missing.toLocaleString()} missing
                      </span>
                    )}
                  </div>
                </div>
                {indexPath && (
                  <div className="mt-2 pt-2 border-t border-line">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteLibrary(indexPath);
                      }}
                      className="text-[10px] text-warn hover:underline"
                    >
                      Remove library & delete scan data
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Type distribution — collapsible */}
        {!collapsed && stats.length > 0 && (
          <>
          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <div className="rounded-lg border border-line bg-surface-2 p-3">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
                Sample Types
              </h2>
              <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
                {stats.map((stat) => (
                  <div key={stat.type} className="flex items-center gap-2">
                    <span className="w-24 text-xs text-muted text-right shrink-0">
                      {stat.type}
                    </span>
                    <div className="flex-1 h-4 bg-surface-2 rounded overflow-hidden">
                      <div
                        className="h-full bg-accent rounded"
                        style={{ width: `${stat.percentage}%` }}
                      />
                    </div>
                    <span className="w-28 text-xs text-muted shrink-0">
                      {(stat.count ?? 0).toLocaleString()} ({stat.percentage}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-line bg-surface-2 p-3">
              <TypePieChart stats={stats} total={catalog.total} />
            </div>
          </div>

          {/* Key distribution — only when samples loaded */}
          {samples.length > 0 && (
            <KeyDistribution samples={samples} />
          )}
        </>
        )}
      </div>
    </div>
  );
}
