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
    <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
      <div className="px-6 py-3 space-y-3">
        {/* Library cards — always visible */}
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {libraries.length} {libraries.length === 1 ? "library" : "libraries"} loaded
          </h2>
          {stats.length > 0 && (
            <button
              onClick={() => setCollapsed((c) => !c)}
              className="text-xs text-gray-500 hover:text-gray-800 transition-colors"
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
                className={`rounded-lg border p-3 text-left transition-all ${
                  isActive
                    ? "border-teal-500 bg-teal-50 dark:bg-teal-950 shadow-md ring-1 ring-teal-500"
                    : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm hover:border-teal-400 hover:shadow-md"
                }`}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300">
                  {lib.name}
                </h3>
                <p className="mt-0.5 text-base font-medium text-gray-900 dark:text-gray-100">
                  {(lib.total ?? 0).toLocaleString()} samples
                </p>
                <div className="mt-1 flex gap-3 text-xs text-gray-500">
                  <span>{(lib.available ?? 0).toLocaleString()} available</span>
                  {(lib.missing ?? 0) > 0 && (
                    <span className="text-amber-600">
                      {lib.missing.toLocaleString()} missing
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Type distribution — collapsible */}
        {!collapsed && stats.length > 0 && (
          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-3">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                Sample Types
              </h2>
              <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
                {stats.map((stat) => (
                  <div key={stat.type} className="flex items-center gap-2">
                    <span className="w-24 text-xs text-gray-600 text-right shrink-0">
                      {stat.type}
                    </span>
                    <div className="flex-1 h-4 bg-gray-200 rounded overflow-hidden">
                      <div
                        className="h-full bg-teal-600 rounded"
                        style={{ width: `${stat.percentage}%` }}
                      />
                    </div>
                    <span className="w-28 text-xs text-gray-500 shrink-0">
                      {(stat.count ?? 0).toLocaleString()} ({stat.percentage}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-3">
              <TypePieChart stats={stats} total={catalog.total} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
