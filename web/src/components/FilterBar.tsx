import { useMemo, useState, useEffect } from "react";
import { useAppStore } from "../store/useAppStore";
import { uniqueValues } from "../utils/filters";

export default function FilterBar() {
  const samples = useAppStore((s) => s.samples);
  const filters = useAppStore((s) => s.filters);
  const setFilter = useAppStore((s) => s.setFilter);
  const resetFilters = useAppStore((s) => s.resetFilters);

  const [searchInput, setSearchInput] = useState(filters.search);
  useEffect(() => {
    const timer = setTimeout(() => setFilter("search", searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput, setFilter]);

  const options = useMemo(
    () => ({
      categories: uniqueValues(samples, "category"),
      types: uniqueValues(samples, "type"),
      keys: ["Unsorted", ...uniqueValues(samples, "key")],
      sources: uniqueValues(samples, "source"),
      brightness: uniqueValues(samples, "brightness"),
      warmth: uniqueValues(samples, "warmth"),
    }),
    [samples],
  );

  const hasFilters = Object.entries(filters).some(([k, v]) => {
    if (k === "confidence") return v > 0;
    if (k === "unsortedOnly") return v === true;
    return v !== "";
  });

  return (
    <div className="bg-surface border-b border-line px-4 py-3">
      <div className="flex flex-wrap gap-3 items-end">
        <Field label="Search">
          <input
            type="text"
            placeholder="Name, key, path, type"
            className="input-base w-44 h-8 text-sm"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </Field>

        <Field label="Playback">
          <Select
            value={filters.playback}
            onChange={(v) => setFilter("playback", v as "" | "available" | "missing")}
            options={["", "available", "missing"]}
            labels={["All playback", "Playable", "Missing"]}
          />
        </Field>

        <Field label="Category">
          <Select
            value={filters.category}
            onChange={(v) => setFilter("category", v)}
            options={["", ...options.categories]}
            labels={["All categories", ...options.categories]}
          />
        </Field>

        <Field label="Type">
          <Select
            value={filters.type}
            onChange={(v) => setFilter("type", v)}
            options={["", ...options.types]}
            labels={["All types", ...options.types]}
          />
        </Field>

        <Field label="Key / Root">
          <Select
            value={filters.key}
            onChange={(v) => setFilter("key", v)}
            options={["", ...options.keys]}
            labels={["All keys", ...options.keys]}
          />
        </Field>

        <Field label="Source">
          <Select
            value={filters.source}
            onChange={(v) => setFilter("source", v)}
            options={["", ...options.sources]}
            labels={["All sources", ...options.sources]}
          />
        </Field>

        <Field label="Brightness">
          <Select
            value={filters.brightness}
            onChange={(v) => setFilter("brightness", v)}
            options={["", ...options.brightness]}
            labels={["Any brightness", ...options.brightness]}
          />
        </Field>

        <Field label="Warmth">
          <Select
            value={filters.warmth}
            onChange={(v) => setFilter("warmth", v)}
            options={["", ...options.warmth]}
            labels={["Any warmth", ...options.warmth]}
          />
        </Field>

        <Field label="BPM">
          <div className="flex gap-1">
            <input
              type="number"
              placeholder="Min"
              className="input-base w-16 h-8 text-sm"
              value={filters.bpmMin}
              onChange={(e) => setFilter("bpmMin", e.target.value)}
            />
            <input
              type="number"
              placeholder="Max"
              className="input-base w-16 h-8 text-sm"
              value={filters.bpmMax}
              onChange={(e) => setFilter("bpmMax", e.target.value)}
            />
          </div>
        </Field>

        <Field label={`Confidence ≥ ${filters.confidence.toFixed(2)}`}>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            className="w-24 accent-accent"
            value={filters.confidence}
            onChange={(e) => setFilter("confidence", parseFloat(e.target.value))}
          />
        </Field>

        <label className="flex items-center gap-1.5 text-xs text-muted font-sans cursor-pointer self-center">
          <input
            type="checkbox"
            checked={filters.unsortedOnly}
            onChange={(e) => setFilter("unsortedOnly", e.target.checked)}
          />
          Unsorted only
        </label>

        {hasFilters && (
          <button
            onClick={resetFilters}
            className="text-xs text-accent hover:underline self-center"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="chip-label">{label}</span>
      {children}
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
  labels,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  labels: string[];
}) {
  return (
    <select
      className="input-base h-8 text-sm"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((opt, i) => (
        <option key={opt} value={opt}>
          {labels[i]}
        </option>
      ))}
    </select>
  );
}
