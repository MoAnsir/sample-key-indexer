import type { CatalogResponse } from "../types/api";

interface DashboardProps {
  catalog: CatalogResponse;
  onLibrarySelect: (libraryId: string) => void;
}

export default function Dashboard({ catalog, onLibrarySelect }: DashboardProps) {
  const libraries = catalog.libraries ?? [];
  const stats = catalog.stats ?? [];

  return (
    <div className="p-6 space-y-6">
      {/* Library cards */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
          Libraries
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {libraries.map((lib) => (
            <button
              key={lib.id}
              onClick={() => onLibrarySelect(lib.id)}
              className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm text-left hover:border-teal-400 hover:shadow-md transition-all"
            >
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
                {lib.name}
              </h3>
              <p className="mt-1 text-lg font-medium text-gray-900">
                {(lib.total ?? 0).toLocaleString()} samples
              </p>
              <div className="mt-2 flex gap-3 text-sm text-gray-500">
                <span>{(lib.available ?? 0).toLocaleString()} available</span>
                {(lib.missing ?? 0) > 0 && (
                  <span className="text-amber-600">
                    {lib.missing.toLocaleString()} missing
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Type distribution */}
      {stats.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
            Sample Types
          </h2>
          <div className="space-y-2">
            {stats.map((stat) => (
              <div key={stat.type} className="flex items-center gap-3">
                <span className="w-28 text-sm text-gray-600 text-right">
                  {stat.type}
                </span>
                <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden">
                  <div
                    className="h-full bg-teal-600 rounded"
                    style={{ width: `${stat.percentage}%` }}
                  />
                </div>
                <span className="w-36 text-sm text-gray-500">
                  {(stat.count ?? 0).toLocaleString()} ({stat.percentage}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
