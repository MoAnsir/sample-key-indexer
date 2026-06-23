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
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Notes: {record.notes.join(" ")}
        </p>
      )}
    </div>
  );
}

interface CompatibleKeysCardProps {
  keys: CompatibleKey[];
}

export function CompatibleKeysCard({ keys }: CompatibleKeysCardProps) {
  if (keys.length === 0) return null;
  return (
    <div>
      <SectionLabel>Compatible Keys</SectionLabel>
      <div className="space-y-2">
        {keys.map((k) => (
          <div key={k.label} className="card">
            <div className="flex items-baseline gap-2">
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">{k.label}</span>
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{k.scale}</span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {(k.diatonic_chords ?? k.chords ?? []).join(" / ")}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

interface ProgressionsCardProps {
  progressions: Progression[];
  sampleId: number;
}

export function ProgressionsCard({ progressions, sampleId }: ProgressionsCardProps) {
  if (progressions.length === 0) return null;
  return (
    <div>
      <SectionLabel>Progressions to Try</SectionLabel>
      <div className="space-y-2">
        {progressions.map((p, i) => (
          <div key={p.name} className="card">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  {p.name}
                </span>
                <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">{p.numerals}</span>
              </div>
              <a
                href={getMidiUrl(sampleId, i)}
                download
                className="px-2.5 py-1 text-xs font-medium rounded bg-teal-600 text-white hover:bg-teal-700 transition-colors"
              >
                MIDI
              </a>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              {p.progression.join(" → ")}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              Mood: {p.mood}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

interface MoodCardProps {
  primary: string;
  supporting: string[];
  transitions: { label: string; why: string }[];
}

export function MoodCard({ primary, supporting, transitions }: MoodCardProps) {
  return (
    <div>
      <SectionLabel>Mood & Transitions</SectionLabel>
      <div className="card space-y-2">
        <p className="text-sm text-gray-800 dark:text-gray-200">
          <span className="font-semibold">{primary}</span>
          {supporting.length > 0 && (
            <span className="text-gray-500 dark:text-gray-400">
              {" "}· {supporting.join(", ")}
            </span>
          )}
        </p>
        {transitions.length > 0 && (
          <div className="space-y-1">
            {transitions.map((t) => (
              <p key={t.label} className="text-xs text-gray-500 dark:text-gray-400">
                → <span className="font-medium text-gray-700 dark:text-gray-300">{t.label}</span>{" "}
                {t.why}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
