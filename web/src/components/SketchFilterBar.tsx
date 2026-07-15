import { useMemo, useState, useEffect } from "react";
import { useAppStore, applyFilters } from "../store/useAppStore";
import { uniqueValues } from "../utils/filters";

export default function SketchFilterBar() {
  const samples = useAppStore((s) => s.samples);
  const filters = useAppStore((s) => s.filters);
  const setFilter = useAppStore((s) => s.setFilter);
  const resetFilters = useAppStore((s) => s.resetFilters);

  const sketchSamples = useMemo(
    () => samples.filter((s) => s.source_kind === "sketch"),
    [samples],
  );

  const isSketchLibrary = sketchSamples.length > 0;

  // Debounced search — update store 300ms after typing stops
  const [searchInput, setSearchInput] = useState(filters.search);
  useEffect(() => {
    setSearchInput(filters.search);
  }, [filters.search]);
  useEffect(() => {
    const timer = setTimeout(() => setFilter("search", searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput, setFilter]);

  const options = useMemo(
    () => ({
      keys: uniqueValues(sketchSamples, "key"),
      types: uniqueValues(sketchSamples, "type"),
    }),
    [sketchSamples],
  );

  const matchCount = useMemo(
    () => applyFilters(sketchSamples, filters).length,
    [sketchSamples, filters],
  );

  const hasFilters =
    filters.search !== "" || filters.key !== "" || filters.type !== "";

  if (!isSketchLibrary) return null;

  return (
    <div className="bg-surface border-b border-line px-4 py-3">
      <div className="flex flex-wrap gap-3 items-end">
        <Field label="Search sketches">
          <input
            type="text"
            placeholder="Name, key, type"
            className="input-base w-44"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </Field>

        <Field label="Key">
          <select
            className="input-base"
            value={filters.key}
            onChange={(e) => setFilter("key", e.target.value)}
          >
            <option value="">All keys</option>
            {options.keys.map((k) => (
              <option key={k} value={k}>
                {k.replace("_", " ")}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Type">
          <select
            className="input-base"
            value={filters.type}
            onChange={(e) => setFilter("type", e.target.value)}
          >
            <option value="">All types</option>
            {options.types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </Field>

        <div className="flex items-center gap-3 self-end pb-0.5">
          <span className="text-xs text-muted font-mono">
            {matchCount} of {sketchSamples.length} sketch
            {sketchSamples.length !== 1 ? "es" : ""}
          </span>

          {hasFilters && (
            <button
              onClick={resetFilters}
              className="text-xs text-accent hover:text-accent underline"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-medium text-muted uppercase tracking-wide">
        {label}
      </span>
      {children}
    </div>
  );
}
