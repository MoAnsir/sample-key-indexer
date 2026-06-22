import { useState } from "react";
import type { CatalogResponse } from "../types/api";

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
    <div className="border-b border-gray-200 bg-white">
      {/* Toggle bar */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-6 py-2 text-xs font-medium uppercase tracking-wide text-gray-500 hover:bg-gray-50 transition-colors"
      >
        <span>
          {libraries.length} {libraries.length === 1 ? "library" : "libraries"} loaded
        </span>
        <span>{collapsed ? "▼ Show" : "▲ Hide"}</span>
      </button>

      {!collapsed && (
        <div className="px-6 pb-4 space-y-4">
          {/* Library cards */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {libraries.map((lib) => {
              const isActive = lib.id === activeLibraryId;
              return (
                <button
                  key={lib.id}
                  onClick={() => onLibrarySelect(lib.id)}
                  className={`rounded-lg border p-3 text-left transition-all ${
                    isActive
                      ? "border-teal-500 bg-teal-50 shadow-md ring-1 ring-teal-500"
                      : "border-gray-200 bg-white shadow-sm hover:border-teal-400 hover:shadow-md"
                  }`}
                >
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-700">
                    {lib.name}
                  </h3>
                  <p className="mt-0.5 text-base font-medium text-gray-900">
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

          {/* Type distribution */}
          {stats.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
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
          )}
        </div>
      )}
    </div>
  );
}
