import { useState } from "react";
import type { CatalogResponse } from "../types/api";
import TypePieChart from "./TypePieChart";

interface DashboardProps {
  catalog: CatalogResponse;
  activeLibraryId: string;
  onLibrarySelect: (libraryId: string) => void;
}

export default function Dashboard({ catalog, activeLibraryId, onLibrarySelect }: DashboardProps) {
  const [collapsed, setCollapsed] = useState(false);
  const libraries = catalog.libraries ?? [];
  const stats = catalog.stats ?? [];

  return (
    <div className="border-b border-line bg-surface">
      <div className="px-6 py-3 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="chip-label">
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
            return (
              <button
                key={lib.id}
                onClick={() => onLibrarySelect(lib.id)}
                className={`rounded-panel border p-3 text-left transition-all ${
                  isActive
                    ? "border-accent bg-accent-soft shadow-card"
                    : "border-line bg-surface shadow-sm hover:border-accent hover:shadow-card"
                }`}
              >
                <h3 className="chip-label">{lib.name}</h3>
                <p className="mt-0.5 text-base font-display font-medium text-ink">
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
              </button>
            );
          })}
        </div>

        {!collapsed && stats.length > 0 && (
          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <div className="card">
              <h2 className="section-label">Sample Types</h2>
              <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
                {stats.map((stat) => (
                  <div key={stat.type} className="flex items-center gap-2">
                    <span className="w-24 text-xs text-muted text-right shrink-0 font-sans">
                      {stat.type}
                    </span>
                    <div className="flex-1 h-4 bg-surface-2 rounded overflow-hidden">
                      <div
                        className="h-full bg-accent rounded"
                        style={{ width: `${stat.percentage}%` }}
                      />
                    </div>
                    <span className="w-28 text-xs text-muted shrink-0 font-mono">
                      {(stat.count ?? 0).toLocaleString()} ({stat.percentage}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="card">
              <TypePieChart stats={stats} total={catalog.total} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
