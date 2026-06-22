import { useQuery } from "@tanstack/react-query";
import { fetchCatalog } from "./api/client";
import type { CatalogResponse } from "./types/api";

export default function App() {
  const { data: catalog, isLoading, error } = useQuery<CatalogResponse>({
    queryKey: ["catalog"],
    queryFn: fetchCatalog,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-lg text-gray-500">Loading catalog...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <p className="text-lg text-red-600">Failed to load catalog</p>
          <p className="text-sm text-gray-500 mt-2">{String(error)}</p>
        </div>
      </div>
    );
  }

  if (!catalog) return null;

  const libraries = catalog.libraries ?? [];
  const stats = catalog.stats ?? [];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
              Sample Library
            </p>
            <h1 className="text-2xl font-bold text-gray-900">
              Key Index Browser
            </h1>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-gray-900">
              {(catalog.total ?? 0).toLocaleString()}
            </p>
            <p className="text-sm text-gray-500">
              {catalog.total === 1 ? "sample" : "samples"}
            </p>
          </div>
        </div>
      </header>

      <main className="p-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {libraries.map((lib) => (
            <div
              key={lib.id}
              className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
                {lib.name}
              </h2>
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
            </div>
          ))}
        </div>

        {stats.length > 0 && (
          <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-700 mb-3">
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
                  <span className="w-32 text-sm text-gray-500">
                    {(stat.count ?? 0).toLocaleString()} ({stat.percentage}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
