import type { SketchAnalysis, SketchPayload } from "../api/client";
import ArrangementPanel from "./ArrangementPanel";

interface SketchResultsProps {
  analysis: SketchAnalysis;
  hasNotes: boolean;
  onDownloadMidi: () => void;
  midiBusy: boolean;
  sketchId?: string;
  payload?: SketchPayload;
  sketchName?: string;
}

export default function SketchResults({
  analysis,
  hasNotes,
  onDownloadMidi,
  midiBusy,
  sketchId,
  payload,
  sketchName,
}: SketchResultsProps) {
  const record = analysis.context.musical_record;
  const mood = analysis.context.mood_profile;
  const compat = analysis.context.compatibility;

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryChip label="Key" value={record.key ?? "—"} />
        <SummaryChip label="Mood" value={mood.primary} />
        <SummaryChip label="BPM" value={String(record.bpm ?? "—")} />
        <SummaryChip label="Scale" value={record.scale ?? "—"} />
      </div>

      <div className="rounded-control border border-line bg-surface-2 px-3 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">
          {hasNotes ? "Notes you played" : "Scale notes"}
        </p>
        <p className="text-sm font-medium text-ink">{record.notes.join("  ")}</p>
      </div>

      {analysis.out_of_scale_notes.length > 0 && (
        <div className="rounded border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn">
          Out-of-scale notes: {analysis.out_of_scale_notes.join(", ")} — these fall outside{" "}
          {record.scale}. Intentional color, or worth double-checking.
        </div>
      )}

      {/* MIDI download */}
      {hasNotes && (
        <button
          onClick={onDownloadMidi}
          disabled={midiBusy}
          className="w-full px-4 py-2 text-sm font-medium rounded-control border border-accent text-accent hover:bg-accent-soft disabled:opacity-50"
        >
          {midiBusy ? "Generating MIDI..." : "⬇ Download your notes as MIDI"}
        </button>
      )}

      {/* Compatible keys */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
          Compatible Keys
        </h3>
        <div className="space-y-1.5">
          {compat.keys.map((k) => (
            <div
              key={k.label}
              className="rounded-control border border-line bg-surface-2 px-3 py-2 flex flex-wrap items-baseline gap-x-3 gap-y-1"
            >
              <span className="text-xs text-muted w-32 shrink-0">{k.label}</span>
              <span className="text-sm font-medium text-ink">{k.scale}</span>
              {k.chords.length > 0 && (
                <span className="text-xs text-faint font-mono">{k.chords.join(" · ")}</span>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Progressions */}
      {compat.progressions.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
            Progressions to Try
          </h3>
          <div className="space-y-1.5">
            {compat.progressions.map((p) => (
              <div key={p.name} className="rounded-control border border-line bg-surface-2 px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-medium text-ink">{p.name}</p>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-soft text-accent">
                    {p.mood}
                  </span>
                </div>
                <p className="text-sm text-ink font-mono mt-0.5">
                  {p.progression.join(" – ")}
                  <span className="text-faint ml-2 text-xs">({p.roman.join(" – ")})</span>
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Mood & transitions */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
          Mood & Transitions
        </h3>
        <div className="rounded-control border border-line bg-surface-2 px-3 py-2 mb-1.5">
          <p className="text-sm text-ink">
            Primary mood: <span className="font-medium">{mood.primary}</span>
            {mood.supporting.length > 0 && (
              <span className="text-muted"> · supporting: {mood.supporting.join(", ")}</span>
            )}
          </p>
        </div>
        <div className="space-y-1">
          {analysis.context.transition_suggestions.map((t) => (
            <p key={t.label} className="text-xs text-muted px-1">
              <span className="text-ink font-medium">{t.label}</span> — {t.why}
            </p>
          ))}
        </div>
      </section>

      {/* Arrangement engine — only available when there are notes to expand */}
      {hasNotes && (sketchId || payload) && (
        <div className="border-t border-line pt-4">
          <ArrangementPanel sketchId={sketchId} payload={payload} sketchName={sketchName} />
        </div>
      )}
    </div>
  );
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-control border border-line bg-surface-2 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="text-sm font-medium text-ink">{value}</p>
    </div>
  );
}
