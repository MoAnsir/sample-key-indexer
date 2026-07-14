import { useState, useCallback } from "react";
import {
  generateArrangement,
  downloadArrangementMidi,
  type ArrangementRequest,
  type ArrangementResult,
  type ArrangementSection,
  type SketchPayload,
} from "../api/client";

interface ArrangementPanelProps {
  sketchId?: string;
  payload?: SketchPayload;
  sketchName?: string;
}

const TARGET_BAR_OPTIONS = [8, 12, 16, 32] as const;

const STRATEGY_OPTIONS: { id: string; label: string; description: string }[] = [
  { id: "humanize", label: "Humanize", description: "Vary velocity per note for a live feel" },
  { id: "ab", label: "A/B Sections", description: "Second half transposed up a 4th" },
  { id: "fill", label: "Fill", description: "Add a rhythmic fill on the last beat" },
  { id: "sparse", label: "Breakdown", description: "Sparse tail — root note only" },
];

const SECTION_COLORS: Record<string, string> = {
  A: "bg-blue-500/20 border-blue-500/40 text-blue-400",
  B: "bg-indigo-500/20 border-indigo-500/40 text-indigo-400",
  Breakdown: "bg-zinc-500/20 border-zinc-500/40 text-zinc-400",
  Fill: "bg-amber-500/20 border-amber-500/40 text-amber-400",
  Main: "bg-accent/20 border-accent/40 text-accent",
};

function sectionColor(label: string): string {
  return SECTION_COLORS[label] ?? "bg-surface-2 border-line text-muted";
}

export default function ArrangementPanel({ sketchId, payload, sketchName }: ArrangementPanelProps) {
  const [targetBars, setTargetBars] = useState<number>(16);
  const [strategies, setStrategies] = useState<Set<string>>(new Set(["humanize", "ab"]));
  const [result, setResult] = useState<ArrangementResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [midibusy, setMidiBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleStrategy = useCallback((id: string) => {
    setStrategies((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const buildRequest = useCallback((): ArrangementRequest => ({
    ...(sketchId ? { sketch_id: sketchId } : { payload }),
    target_bars: targetBars,
    strategies: [...strategies],
  }), [sketchId, payload, targetBars, strategies]);

  const handleBuild = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await generateArrangement(buildRequest());
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }, [buildRequest]);

  const handleDownload = useCallback(async () => {
    setMidiBusy(true);
    try {
      const blob = await downloadArrangementMidi(buildRequest());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${sketchName ?? "arrangement"}_arrangement.mid`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(String(err));
    } finally {
      setMidiBusy(false);
    }
  }, [buildRequest, sketchName]);

  return (
    <section className="space-y-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
        Arrangement Engine
      </h3>

      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-end">
        {/* Target bars */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted mb-1">Length</p>
          <div className="flex gap-1">
            {TARGET_BAR_OPTIONS.map((b) => (
              <button
                key={b}
                onClick={() => setTargetBars(b)}
                className={`px-2.5 py-1 text-xs font-medium rounded-chip border transition-colors ${
                  targetBars === b
                    ? "bg-accent text-white border-accent"
                    : "bg-surface-2 border-line text-muted hover:text-ink"
                }`}
              >
                {b} bars
              </button>
            ))}
          </div>
        </div>

        {/* Strategies */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted mb-1">Strategies</p>
          <div className="flex flex-wrap gap-1.5">
            {STRATEGY_OPTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => toggleStrategy(s.id)}
                title={s.description}
                className={`px-2.5 py-1 text-xs font-medium rounded-chip border transition-colors ${
                  strategies.has(s.id)
                    ? "bg-accent text-white border-accent"
                    : "bg-surface-2 border-line text-muted hover:text-ink"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleBuild}
          disabled={busy}
          className="px-4 py-1.5 text-xs font-medium rounded-control bg-accent text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {busy ? "Building…" : "Build Arrangement"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-warn">{error}</p>
      )}

      {result && (
        <div className="space-y-3">
          {/* Section map */}
          <div className="flex flex-wrap gap-2">
            {result.arrangement.sections.map((sec, i) => (
              <SectionChip key={i} section={sec} />
            ))}
          </div>

          {/* Stats row */}
          <div className="flex gap-4 text-xs text-muted">
            <span>{result.arrangement.total_bars} bars</span>
            <span>{result.arrangement.bpm} BPM</span>
            {result.arrangement.tonic && (
              <span>{result.arrangement.tonic} {result.arrangement.mode}</span>
            )}
            <span>{result.arrangement.sections.reduce((n, s) => n + s.note_events.length, 0)} notes</span>
          </div>

          <button
            onClick={handleDownload}
            disabled={midibusy}
            className="px-3 py-1.5 text-xs font-medium rounded-control border border-accent text-accent hover:bg-accent-soft disabled:opacity-50 transition-colors"
          >
            {midibusy ? "Rendering…" : "⬇ Download Arrangement MIDI"}
          </button>
        </div>
      )}
    </section>
  );
}

function SectionChip({ section }: { section: ArrangementSection }) {
  const length = section.bar_end - section.bar_start;
  const colors = sectionColor(section.label);
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-control border text-xs ${colors}`}>
      <span className="font-semibold">{section.label}</span>
      <span className="opacity-60">{length} bar{length !== 1 ? "s" : ""}</span>
      <span className="opacity-40 text-[10px]">{section.variation}</span>
    </div>
  );
}
