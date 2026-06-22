import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCatalog, fetchSamples } from "./api/client";
import { useAppStore } from "./store/useAppStore";
import Dashboard from "./components/Dashboard";
import FilterBar from "./components/FilterBar";
import SampleTable from "./components/SampleTable";
import SampleDetailPanel from "./components/SampleDetailPanel";
import ReviewTab from "./components/ReviewTab";
import type { CatalogResponse } from "./types/api";

export default function App() {
  const { data: catalog, isLoading, error } = useQuery<CatalogResponse>({
    queryKey: ["catalog"],
    queryFn: fetchCatalog,
  });

  const setCatalog = useAppStore((s) => s.setCatalog);
  const setSamples = useAppStore((s) => s.setSamples);
  const samples = useAppStore((s) => s.samples);
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const filters = useAppStore((s) => s.filters);
  const setFilter = useAppStore((s) => s.setFilter);
  const loading = useAppStore((s) => s.loading);
  const loadingMessage = useAppStore((s) => s.loadingMessage);
  const setLoading = useAppStore((s) => s.setLoading);

  if (catalog && !useAppStore.getState().catalog) {
    setCatalog(catalog);
  }

  const loadLibrary = useCallback(
    async (libraryId: string) => {
      setLoading(true, "Fetching samples...");
      setFilter("libraryId", libraryId);
      try {
        const allSamples = [];
        let offset = 0;
        const limit = 15000;
        // eslint-disable-next-line no-constant-condition
        while (true) {
          setLoading(true, `Fetching samples... (${offset.toLocaleString()} loaded)`);
          const response = await fetchSamples(libraryId, offset, limit);
          allSamples.push(...response.samples);
          if (response.returned < limit) break;
          offset += limit;
        }
        setSamples(allSamples);
        setActiveTab("browse");
      } catch (err) {
        console.error("Failed to load library:", err);
      } finally {
        setLoading(false);
      }
    },
    [setSamples, setActiveTab, setLoading, setFilter],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-lg text-gray-500">Loading catalog...</p>
      </div>
    );
  }

  if (error || !catalog) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <p className="text-lg text-red-600">Failed to load catalog</p>
          <p className="text-sm text-gray-500 mt-2">{String(error ?? "No data")}</p>
        </div>
      </div>
    );
  }

  const hasLibrary = samples.length > 0;

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 max-w-[1600px] mx-auto w-full">
      {/* Loading overlay */}
      {loading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg px-8 py-6 shadow-xl text-center">
            <div className="animate-spin h-8 w-8 border-4 border-teal-600 border-t-transparent rounded-full mx-auto" />
            <p className="mt-3 text-sm text-gray-600">{loadingMessage}</p>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-widest text-gray-400">
                Sample Library
              </p>
              <h1 className="text-xl font-bold text-gray-900">
                Key Index Browser
              </h1>
            </div>

            {hasLibrary && (
              <nav className="flex gap-1">
                <TabButton
                  active={activeTab === "browse"}
                  onClick={() => setActiveTab("browse")}
                >
                  Browse
                </TabButton>
                <TabButton
                  active={activeTab === "review"}
                  onClick={() => setActiveTab("review")}
                >
                  Review
                </TabButton>
              </nav>
            )}
          </div>

          <div className="text-right">
            <p className="text-2xl font-bold text-gray-900">
              {(catalog.total ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-gray-500">
              {hasLibrary
                ? `${samples.length.toLocaleString()} loaded`
                : `${catalog.total === 1 ? "sample" : "samples"}`}
            </p>
          </div>
        </div>
      </header>

      {/* Dashboard — always visible, collapsible */}
      <Dashboard
        catalog={catalog}
        activeLibraryId={filters.libraryId}
        onLibrarySelect={loadLibrary}
      />

      {/* Sample detail slide-over */}
      <SampleDetailPanel />

      {/* Browse / Review content */}
      {hasLibrary && (
        <div className="flex flex-col flex-1 min-h-0">
          <FilterBar />
          {activeTab === "browse" ? (
            <SampleTable />
          ) : (
            <ReviewTab />
          )}
        </div>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
        active
          ? "bg-teal-600 text-white"
          : "text-gray-600 hover:bg-gray-100"
      }`}
    >
      {children}
    </button>
  );
}
