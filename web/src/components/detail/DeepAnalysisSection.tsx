import SectionLabel from "../ui/SectionLabel";
import ChipGrid from "../ui/ChipGrid";
import type { SampleDetail } from "../../types/api";

export default function DeepAnalysisSection({ detail }: { detail: SampleDetail }) {
  const chips: [string, string | number | null | undefined][] = [
    ["Deep Key", detail.deep_key],
    ["Deep Key Conf", detail.deep_key_confidence?.toFixed(2)],
    ["Deep BPM", detail.deep_bpm != null ? `${detail.deep_bpm.toFixed(1)} BPM` : null],
    ["Deep BPM Conf", detail.deep_bpm_confidence?.toFixed(2)],
    ["Deep Tuning", detail.deep_tuning_hz != null ? `${detail.deep_tuning_hz.toFixed(2)} Hz` : null],
    ["Deep Route", detail.deep_route_family],
    ["Deep Status", detail.deep_analysis_status],
    ["Note Count", detail.deep_note_count],
    ["Onset Count", detail.deep_onset_count],
    ["Timing Conf", detail.deep_timing_confidence?.toFixed(2)],
    ["Note Conf", detail.deep_note_confidence?.toFixed(2)],
  ];

  const engines = [
    detail.deep_tonal_backend,
    detail.deep_chord_backend,
    detail.deep_timing_backend,
    detail.deep_tuning_backend,
    detail.deep_note_backend,
  ].filter(Boolean);

  return (
    <div>
      <SectionLabel>Deep Analysis</SectionLabel>
      <ChipGrid chips={chips} />
      {engines.length > 0 && (
        <p className="mt-2 text-xs text-muted font-mono">
          Engines: {engines.join(" · ")}
        </p>
      )}
      {(detail.deep_chords?.length ?? 0) > 0 && (
        <p className="mt-1 text-xs text-muted font-mono">
          Chords: {detail.deep_chords.slice(0, 12).join(", ")}
          {detail.deep_chords.length > 12 && ` +${detail.deep_chords.length - 12} more`}
        </p>
      )}
      {(detail.deep_note_events?.length ?? 0) > 0 && (
        <p className="mt-1 text-xs text-muted font-mono">
          Notes: {detail.deep_note_events.slice(0, 8).map((e) => e.note).join(", ")}
          {detail.deep_note_events.length > 8 && ` +${detail.deep_note_events.length - 8} more`}
        </p>
      )}
    </div>
  );
}
