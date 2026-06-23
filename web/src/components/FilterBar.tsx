import { useMemo } from "react";
import { useAppStore } from "../store/useAppStore";
import type { Sample } from "../types/api";

function unique(samples: Sample[], key: keyof Sample): string[] {
  const set = new Set<string>();
  for (const s of samples) {
    const v = s[key];
    if (v != null && v !== "") set.add(String(v));
  }
  return [...set].sort();
}

export default function FilterBar() {
  const samples = useAppStore((s) => s.samples);
  const filters = useAppStore((s) => s.filters);
  const setFilter = useAppStore((s) => s.setFilter);
  const resetFilters = useAppStore((s) => s.resetFilters);

  const options = useMemo(
    () => ({
      categories: unique(samples, "category"),
      types: unique(samples, "type"),
      keys: ["Unsorted", ...unique(samples, "key")],
      sources: unique(samples, "source"),
      brightness: unique(samples, "brightness"),
      warmth: unique(samples, "warmth"),
    }),
    [samples],
  );

  const hasFilters = Object.entries(filters).some(([k, v]) => {
    if (k === "confidence") return v > 0;
    if (k === "unsortedOnly") return v === true;
    return v !== "";
  });

  return (
    <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-4 py-3">
      <div className="flex flex-wrap gap-3 items-end">
        <Field label="Search">
          <input
            type="text"
            placeholder="Name, key, path, type"
            className="input-base w-44"
            value={filters.search}
            onChange={(e) => setFilter("search", e.target.value)}
          />
        </Field>

        <Field label="Playback">
          <Select
            value={filters.playback}
            onChange={(v) => setFilter("playback", v as FilterBar.Playback)}
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
              className="input-base w-16"
              value={filters.bpmMin}
              onChange={(e) => setFilter("bpmMin", e.target.value)}
            />
            <input
              type="number"
              placeholder="Max"
              className="input-base w-16"
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
            className="w-24"
            value={filters.confidence}
            onChange={(e) => setFilter("confidence", parseFloat(e.target.value))}
          />
        </Field>

        <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer self-center">
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
            className="text-xs text-teal-700 hover:text-teal-900 underline self-center"
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
      <span className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </span>
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
      className="input-base"
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

namespace FilterBar {
  export type Playback = "" | "available" | "missing";
}
