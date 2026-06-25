import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCatalog, fetchSamples } from "./api/client";
import { useAppStore, type Theme } from "./store/useAppStore";
import Dashboard from "./components/Dashboard";
import FilterBar from "./components/FilterBar";
import SampleTable from "./components/SampleTable";
import SampleDetailPanel from "./components/SampleDetailPanel";
import ReviewTab from "./components/ReviewTab";
import ErrorBoundary from "./components/ui/ErrorBoundary";
import Logo from "./assets/logo.svg";
import type { CatalogResponse } from "./types/api";

const THEMES: { value: Theme; label: string }[] = [
  { value: "studio", label: "Studio" },
  { value: "indigo", label: "Indigo" },
  { value: "paper", label: "Paper" },
  { value: "dark", label: "Dark" },
];

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
  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);

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
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <p className="text-lg text-muted font-sans">Loading catalog...</p>
      </div>
    );
  }

  if (error || !catalog) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <div className="text-center">
          <p className="text-lg text-warn">Failed to load catalog</p>
          <p className="text-sm text-muted mt-2">{String(error ?? "No data")}</p>
        </div>
      </div>
    );
  }

  const hasLibrary = samples.length > 0;

  return (
    <div className="flex flex-col min-h-screen bg-bg max-w-[1600px] mx-auto w-full">
      {/* Loading overlay */}
      {loading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface rounded-panel px-8 py-6 shadow-pop text-center">
            <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full mx-auto" />
            <p className="mt-3 text-sm text-muted font-sans">{loadingMessage}</p>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="bg-surface border-b border-line px-6 py-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <img src={Logo} alt="Key Index" className="w-8 h-8 rounded-lg" />
              <div>
                <p className="chip-label tracking-widest">Sample Library</p>
                <h1 className="text-lg font-display font-bold text-ink">
                  Key Index Browser
                </h1>
              </div>
            </div>

            {hasLibrary && (
              <div className="flex gap-0.5 bg-surface-2 border border-line rounded-control p-0.5">
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
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            {/* Theme switcher */}
            <div className="flex gap-0.5 bg-surface-2 border border-line rounded-control p-0.5">
              {THEMES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTheme(t.value)}
                  className={`px-3 py-1.5 text-xs font-sans font-medium rounded-chip transition-colors ${
                    theme === t.value
                      ? "bg-surface text-ink shadow-sm"
                      : "text-muted hover:text-ink"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="text-right">
              <p className="text-2xl font-display font-bold text-ink">
                {(catalog.total ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-muted font-mono">
                {hasLibrary
                  ? `${samples.length.toLocaleString()} loaded`
                  : `${catalog.total === 1 ? "sample" : "samples"}`}
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Dashboard — always visible, collapsible */}
      <ErrorBoundary>
        <Dashboard
          catalog={catalog}
          activeLibraryId={filters.libraryId}
          onLibrarySelect={loadLibrary}
        />
      </ErrorBoundary>

      {/* Sample detail slide-over */}
      <SampleDetailPanel />

      {/* Browse / Review content */}
      {hasLibrary && (
        <div className="flex flex-col flex-1 min-h-0">
          <ErrorBoundary>
            {activeTab === "browse" ? (
              <>
                <FilterBar />
                <SampleTable />
              </>
            ) : (
              <ReviewTab />
            )}
          </ErrorBoundary>
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
      className={`px-4 py-1.5 text-sm font-sans font-medium rounded-chip transition-colors ${
        active
          ? "bg-surface text-ink shadow-sm"
          : "text-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
