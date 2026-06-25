import { create } from "zustand";
import type { Sample, CatalogResponse, SampleDetail } from "../types/api";

export type Theme = "studio" | "indigo" | "paper" | "dark";

export interface FilterState {
  search: string;
  libraryId: string;
  playback: "" | "available" | "missing";
  category: string;
  type: string;
  key: string;
  source: string;
  brightness: string;
  warmth: string;
  bpmMin: string;
  bpmMax: string;
  confidence: number;
  unsortedOnly: boolean;
}

const defaultFilters: FilterState = {
  search: "",
  libraryId: "",
  playback: "",
  category: "",
  type: "",
  key: "",
  source: "",
  brightness: "",
  warmth: "",
  bpmMin: "",
  bpmMax: "",
  confidence: 0,
  unsortedOnly: false,
};

interface AppState {
  catalog: CatalogResponse | null;
  setCatalog: (catalog: CatalogResponse) => void;

  samples: Sample[];
  setSamples: (samples: Sample[]) => void;

  filters: FilterState;
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  resetFilters: () => void;

  sortKey: string;
  sortDirection: "asc" | "desc";
  setSort: (key: string) => void;

  page: number;
  pageSize: number;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;

  selectedSampleId: number | null;
  setSelectedSampleId: (id: number | null) => void;

  sampleDetailCache: Map<number, SampleDetail>;
  cacheSampleDetail: (id: number, detail: SampleDetail) => void;

  activeTab: "browse" | "review";
  setActiveTab: (tab: "browse" | "review") => void;

  loading: boolean;
  loadingMessage: string;
  setLoading: (loading: boolean, message?: string) => void;

  theme: Theme;
  setTheme: (theme: Theme) => void;
  isDark: boolean;
}

export const useAppStore = create<AppState>((set) => ({
  catalog: null,
  setCatalog: (catalog) => set({ catalog }),

  samples: [],
  setSamples: (samples) => set({ samples }),

  filters: { ...defaultFilters },
  setFilter: (key, value) =>
    set((s) => ({ filters: { ...s.filters, [key]: value }, page: 1 })),
  resetFilters: () => set({ filters: { ...defaultFilters }, page: 1 }),

  sortKey: "name",
  sortDirection: "asc",
  setSort: (key) =>
    set((s) => ({
      sortKey: key,
      sortDirection: s.sortKey === key && s.sortDirection === "asc" ? "desc" : "asc",
      page: 1,
    })),

  page: 1,
  pageSize: 100,
  setPage: (page) => set({ page }),
  setPageSize: (pageSize) => set({ pageSize, page: 1 }),

  selectedSampleId: null,
  setSelectedSampleId: (id) => set({ selectedSampleId: id }),

  sampleDetailCache: new Map(),
  cacheSampleDetail: (id, detail) =>
    set((s) => {
      const next = new Map(s.sampleDetailCache);
      next.set(id, detail);
      return { sampleDetailCache: next };
    }),

  activeTab: "browse",
  setActiveTab: (tab) => set({ activeTab: tab }),

  loading: false,
  loadingMessage: "",
  setLoading: (loading, message = "") => set({ loading, loadingMessage: message }),

  theme: (localStorage.getItem("ki-theme") as Theme) ?? "studio",
  setTheme: (theme) => {
    localStorage.setItem("ki-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
    set({ theme, isDark: theme === "dark" });
  },
  isDark: ((localStorage.getItem("ki-theme") as Theme) ?? "studio") === "dark",
}));

export function applyFilters(samples: Sample[], filters: FilterState): Sample[] {
  let result = samples;

  if (filters.search) {
    const q = filters.search.toLowerCase();
    result = result.filter(
      (s) =>
        (s.name ?? "").toLowerCase().includes(q) ||
        (s.key ?? "").toLowerCase().includes(q) ||
        (s.type ?? "").toLowerCase().includes(q) ||
        (s.category ?? "").toLowerCase().includes(q) ||
        (s.file_path ?? "").toLowerCase().includes(q) ||
        (s.library_name ?? "").toLowerCase().includes(q) ||
        (s.source ?? "").toLowerCase().includes(q),
    );
  }
  if (filters.playback) {
    result = result.filter((s) => s.playback_status === filters.playback);
  }
  if (filters.category) {
    result = result.filter((s) => s.category === filters.category);
  }
  if (filters.type) {
    result = result.filter((s) => s.type === filters.type);
  }
  if (filters.key) {
    if (filters.key === "Unsorted") {
      result = result.filter((s) => !s.key && !s.root_note);
    } else {
      result = result.filter((s) => s.key === filters.key || s.root_note === filters.key);
    }
  }
  if (filters.source) {
    result = result.filter((s) => s.source === filters.source);
  }
  if (filters.brightness) {
    result = result.filter((s) => s.brightness === filters.brightness);
  }
  if (filters.warmth) {
    result = result.filter((s) => s.warmth === filters.warmth);
  }
  if (filters.bpmMin) {
    const min = parseFloat(filters.bpmMin);
    if (!isNaN(min)) result = result.filter((s) => (s.bpm ?? 0) >= min);
  }
  if (filters.bpmMax) {
    const max = parseFloat(filters.bpmMax);
    if (!isNaN(max)) result = result.filter((s) => (s.bpm ?? Infinity) <= max);
  }
  if (filters.confidence > 0) {
    result = result.filter((s) => (s.confidence ?? 0) >= filters.confidence);
  }
  if (filters.unsortedOnly) {
    result = result.filter((s) => !s.key && !s.root_note);
  }

  return result;
}

export function sortSamples(
  samples: Sample[],
  key: string,
  direction: "asc" | "desc",
): Sample[] {
  const sorted = [...samples].sort((a, b) => {
    const av = (a as never as Record<string, unknown>)[key];
    const bv = (b as unknown as Record<string, unknown>)[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "number" && typeof bv === "number") return av - bv;
    return String(av).localeCompare(String(bv));
  });
  return direction === "desc" ? sorted.reverse() : sorted;
}
