import { useState, useCallback } from "react";
import { matchSamples, type MatchFilters, type MatchResult, type SketchPayload } from "../api/client";
import { useAppStore } from "../store/useAppStore";
import type { Sample } from "../types/api";

interface MatchPanelProps {
  sketchId?: string;
  payload?: SketchPayload;
}

const FILTER_OPTIONS: { id: keyof MatchFilters; label: string; description: string }[] = [
  { id: "key_compat", label: "Key", description: "Same / relative / dominant key" },
  { id: "freq_slot", label: "Frequency", description: "Complements the sketch's frequency register" },
  { id: "mood", label: "Mood", description: "Brightness / warmth match for the scale mode" },
  { id: "bpm", label: "BPM", description: "±10 BPM, halftime, or doubletime" },
];

const REASON_COLORS: Record<string, string> = {
  "same key":        "bg-good/15 text-good",
  "relative key":    "bg-accent/15 text-accent",
  "dominant move":   "bg-accent/10 text-accent",
  "subdominant move":"bg-accent/10 text-accent",
  "parallel color":  "bg-accent/10 text-accent",
  "same BPM":        "bg-blue-500/15 text-blue-400",
  "halftime":        "bg-blue-500/10 text-blue-400",
  "doubletime":      "bg-blue-500/10 text-blue-400",
};

function reasonColor(r: string): string {
  return REASON_COLORS[r] ?? "bg-surface-2 text-muted";
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 70 ? "bg-good/15 text-good" :
    pct >= 40 ? "bg-accent/15 text-accent" :
    "bg-surface-2 text-muted";
  return (
    <span className={`inline-block px-1.5 py-0.5 text-[10px] font-semibold rounded ${color}`}>
      {pct}%
    </span>
  );
}

function MatchRow({ match, onSelect }: { match: Sample & { score: number; match_reasons: string[] }; onSelect: () => void }) {
  return (
    <tr
      className="hover:bg-accent-soft cursor-pointer transition-colors border-b border-line last:border-0"
      onClick={onSelect}
    >
      <td className="px-3 py-2 text-xs text-ink max-w-[220px] truncate">{match.name}</td>
      <td className="px-3 py-2 text-xs text-muted">{match.key?.replace("_", " ") ?? "—"}</td>
      <td className="px-3 py-2 text-xs text-muted">{match.type ?? "—"}</td>
      <td className="px-3 py-2 text-xs text-muted tabular-nums">
        {match.bpm ? `${Math.round(match.bpm)}` : "—"}
      </td>
      <td className="px-3 py-2">
        <ScoreBadge score={match.score} />
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap gap-1">
          {match.match_reasons.map((r) => (
            <span key={r} className={`text-[10px] px-1.5 py-0.5 rounded ${reasonColor(r)}`}>
              {r}
            </span>
          ))}
        </div>
      </td>
    </tr>
  );
}

export default function MatchPanel({ sketchId, payload }: MatchPanelProps) {
  const [filters, setFilters] = useState<MatchFilters>({
    key_compat: true,
    freq_slot: true,
    mood: true,
    bpm: true,
  });
  const [result, setResult] = useState<MatchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setSelectedSampleId = useAppStore((s) => s.setSelectedSampleId);
  const librarySamples = useAppStore((s) => s.samples);

  const toggleFilter = useCallback((id: keyof MatchFilters) => {
    setFilters((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const handleMatch = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await matchSamples({
        ...(sketchId ? { sketch_id: sketchId } : { sketch: payload }),
        top_n: 50,
        filters,
      });
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }, [sketchId, payload, filters]);

  const noLibrary = librarySamples.length === 0;

  return (
    <section className="space-y-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
        Find Matching Samples
      </h3>

      {noLibrary && (
        <p className="text-xs text-muted rounded-control border border-line bg-surface-2 px-3 py-2">
          Load a library from the Dashboard first — the server needs scanned samples to match against.
        </p>
      )}

      <div className="flex flex-wrap gap-3 items-end">
        {/* Dimension toggles */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted mb-1">Match by</p>
          <div className="flex flex-wrap gap-1.5">
            {FILTER_OPTIONS.map((f) => (
              <button
                key={f.id}
                onClick={() => toggleFilter(f.id)}
                title={f.description}
                className={`px-2.5 py-1 text-xs font-medium rounded-chip border transition-colors ${
                  filters[f.id]
                    ? "bg-accent text-white border-accent"
                    : "bg-surface-2 border-line text-muted hover:text-ink"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleMatch}
          disabled={busy || noLibrary}
          className="px-4 py-1.5 text-xs font-medium rounded-control bg-accent text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {busy ? "Searching…" : "Find Matching Samples"}
        </button>
      </div>

      {error && <p className="text-xs text-warn">{error}</p>}

      {result && (
        <div className="space-y-2">
          <p className="text-xs text-muted">
            {result.matches.length} match{result.matches.length !== 1 ? "es" : ""} from{" "}
            {result.total_searched.toLocaleString()} samples
          </p>

          {result.matches.length === 0 ? (
            <p className="text-xs text-faint px-1">
              No matches found — try enabling more dimensions or loading a larger library.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-control border border-line">
              <table className="w-full text-sm border-collapse min-w-[500px]">
                <thead className="bg-surface-2 sticky top-0">
                  <tr>
                    {["Name", "Key", "Type", "BPM", "Score", "Reasons"].map((h) => (
                      <th
                        key={h}
                        className="px-3 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wide text-muted whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.matches.map((m) => (
                    <MatchRow
                      key={m.id}
                      match={m}
                      onSelect={() => setSelectedSampleId(m.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
