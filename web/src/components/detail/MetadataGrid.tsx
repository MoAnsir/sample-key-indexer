import ChipGrid from "../ui/ChipGrid";
import type { SampleDetail } from "../../types/api";

interface MetadataGridProps {
  detail: SampleDetail;
}

export default function MetadataGrid({ detail }: MetadataGridProps) {
  const chips: [string, string | number | null | undefined][] = [
    ["Key", detail.key],
    ["Root", detail.root_note],
    ["Notes", detail.notes?.join(", ")],
    ["Chords", detail.chords?.slice(0, 6).join(", ")],
    ["BPM", detail.bpm != null ? Math.round(detail.bpm) : null],
    ["Confidence", detail.confidence != null ? detail.confidence.toFixed(2) : null],
    ["Duration", detail.duration != null ? `${detail.duration.toFixed(1)}s` : null],
    ["Format", detail.format],
    ["Sample Rate", detail.sample_rate != null ? `${detail.sample_rate} Hz` : null],
    ["Category", detail.category],
    ["Type", detail.type],
    ["Subtype", detail.subtype],
    ["Source", detail.source],
    ["Brightness", detail.brightness],
    ["Warmth", detail.warmth],
    ["Loudness", detail.rms_db != null ? `${detail.rms_db.toFixed(1)} dB RMS` : null],
    ["Peak", detail.peak_db != null ? `${detail.peak_db.toFixed(1)} dB` : null],
    ["Fundamental", detail.fundamental_freq != null ? `${detail.fundamental_freq.toFixed(1)} Hz` : null],
    ["Centroid", detail.spectral_centroid != null ? `${Math.round(detail.spectral_centroid)} Hz` : null],
    ["Bandwidth", detail.spectral_bandwidth != null ? `${Math.round(detail.spectral_bandwidth)} Hz` : null],
    ["Rolloff", detail.rolloff != null ? `${Math.round(detail.rolloff)} Hz` : null],
    ["Library", detail.library_name],
    ["Reviewed", detail.reviewed ? "Yes" : "No"],
  ];

  return <ChipGrid chips={chips} />;
}
