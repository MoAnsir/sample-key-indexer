import SectionLabel from "../ui/SectionLabel";
import Chip from "../ui/Chip";
import { getMidiUrl } from "../../api/client";
import type { SampleDetail, CompatibleKey, Progression } from "../../types/api";

interface MusicalRecordCardProps {
  record: NonNullable<SampleDetail["musical_record"]>;
}

export function MusicalRecordCard({ record }: MusicalRecordCardProps) {
  return (
    <div>
      <SectionLabel>Musical Record</SectionLabel>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 card">
        <Chip label="Key" value={record.key} />
        <Chip label="Tonic" value={record.tonic} />
        <Chip label="Scale" value={record.scale} />
        <Chip label="BPM" value={record.bpm != null ? `${record.bpm.toFixed(1)}` : null} />
        <Chip label="Tuning" value={record.tuning != null ? `${record.tuning.toFixed(2)} Hz` : null} />
        <Chip label="Confidence" value={record.confidence != null ? record.confidence.toFixed(2) : null} />
      </div>
      {(record.notes?.length ?? 0) > 0 && (
        <p className="mt-2 text-xs text-muted font-mono">
          Notes: {record.notes.join(" ")}
        </p>
      )}
    </div>
  );
}

export function CompatibleKeysCard({ keys }: { keys: CompatibleKey[] }) {
  if (keys.length === 0) return null;
  return (
    <div>
      <SectionLabel>Compatible Keys</SectionLabel>
      <div className="space-y-2">
        {keys.map((k) => (
          <div key={k.label} className="card">
            <div className="flex items-baseline gap-2">
              <span className="text-xs font-sans font-semibold text-muted">{k.label}</span>
              <span className="text-sm font-display font-medium text-ink">{k.scale}</span>
            </div>
            <p className="text-xs text-faint mt-1 font-mono">
              {(k.diatonic_chords ?? k.chords ?? []).join(" / ")}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProgressionsCard({
  progressions,
  sampleId,
}: {
  progressions: Progression[];
  sampleId: number;
}) {
  if (progressions.length === 0) return null;
  return (
    <div>
      <SectionLabel>Progressions to Try</SectionLabel>
      <div className="space-y-2">
        {progressions.map((p, i) => (
          <div key={p.name} className="card">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-display font-semibold text-ink">
                  {p.name}
                </span>
                <span className="ml-2 text-xs text-faint font-mono">{p.numerals}</span>
              </div>
              <a
                href={getMidiUrl(sampleId, i)}
                download
                className="px-2.5 py-1 text-xs font-sans font-medium rounded-control bg-accent text-accent-ink hover:opacity-90 transition-opacity"
              >
                MIDI
              </a>
            </div>
            <p className="text-xs text-muted mt-1 font-mono">
              {p.progression.join(" → ")}
            </p>
            <p className="text-xs text-faint mt-0.5 font-sans">
              Mood: {p.mood}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MoodCard({
  primary,
  supporting,
  transitions,
}: {
  primary: string;
  supporting: string[];
  transitions: { label: string; why: string }[];
}) {
  return (
    <div>
      <SectionLabel>Mood & Transitions</SectionLabel>
      <div className="card space-y-2">
        <p className="text-sm text-ink font-sans">
          <span className="font-semibold">{primary}</span>
          {supporting.length > 0 && (
            <span className="text-muted"> · {supporting.join(", ")}</span>
          )}
        </p>
        {transitions.length > 0 && (
          <div className="space-y-1">
            {transitions.map((t) => (
              <p key={t.label} className="text-xs text-muted font-sans">
                → <span className="font-medium text-ink">{t.label}</span> {t.why}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
