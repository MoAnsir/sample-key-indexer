import { useEffect, useState, useCallback, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSampleDetail, getMidiUrl, postReview } from "../api/client";
import { useAppStore } from "../store/useAppStore";
import AudioPlayer from "./AudioPlayer";
import FrequencyChart from "./FrequencyChart";
import MFCCChart from "./MFCCChart";
import type { SampleDetail, CompatibleKey, Progression } from "../types/api";

const NOTE_ORDER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const BLACK_KEYS = new Set(["C#", "D#", "F#", "G#", "A#"]);

const ANIM_DURATION = 200;

export default function SampleDetailPanel() {
  const selectedId = useAppStore((s) => s.selectedSampleId);
  const setSelectedSampleId = useAppStore((s) => s.setSelectedSampleId);
  const [visible, setVisible] = useState(false);
  const [closing, setClosing] = useState(false);
  const closingRef = useRef(false);

  // Open: when selectedId becomes non-null, show immediately
  useEffect(() => {
    if (selectedId != null) {
      setVisible(true);
      setClosing(false);
      closingRef.current = false;
    }
  }, [selectedId]);

  // Lock body scroll when panel is visible
  useEffect(() => {
    if (!visible) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [visible]);

  const handleClose = useCallback(() => {
    if (closingRef.current) return;
    closingRef.current = true;
    setClosing(true);
    setTimeout(() => {
      setSelectedSampleId(null);
      setVisible(false);
      setClosing(false);
      closingRef.current = false;
    }, ANIM_DURATION);
  }, [setSelectedSampleId]);

  const { data: detail, isLoading, error } = useQuery<SampleDetail>({
    queryKey: ["sample-detail", selectedId],
    queryFn: () => fetchSampleDetail(selectedId!),
    enabled: selectedId != null,
  });

  if (!visible || selectedId == null) return null;

  if (error) {
    return (
      <div className={`fixed inset-0 z-40 flex ${closing ? "animate-fade-out" : "animate-fade-in"}`}>
        <div className="absolute inset-0 bg-black/30" onClick={handleClose} />
        <div className={`relative ml-auto w-full max-w-3xl bg-white shadow-2xl p-6 ${closing ? "animate-slide-out" : "animate-slide-in"}`}>
          <p className="text-red-600">Error loading sample: {String(error)}</p>
          <button onClick={handleClose} className="mt-4 text-sm text-gray-500 underline">Close</button>
        </div>
      </div>
    );
  }

  return (
    <div className={`fixed inset-0 z-40 flex ${closing ? "animate-fade-out" : "animate-fade-in"}`}>
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30"
        onClick={handleClose}
      />

      {/* Panel */}
      <div className={`relative ml-auto w-full max-w-3xl bg-white shadow-2xl overflow-y-auto ${closing ? "animate-slide-out" : "animate-slide-in"}`}>
        <PanelHeader
          name={detail?.name}
          detail={detail}
          sampleId={selectedId}
          onClose={handleClose}
        />

        {isLoading || !detail ? (
          <div className="flex flex-col items-center justify-center h-64 gap-3">
            <div className="animate-spin h-8 w-8 border-4 border-teal-600 border-t-transparent rounded-full" />
            <p className="text-sm text-gray-400">Loading sample details...</p>
          </div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Audio Player */}
            {detail.playback_status === "available" && (
              <AudioPlayer sampleId={selectedId} autoPlay />
            )}
            {detail.playback_status !== "available" && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
                Audio unavailable — source media not mounted
              </div>
            )}

            {/* Metadata grid */}
            <MetadataGrid detail={detail} />

            {/* Frequency & MFCC charts */}
            <FrequencyChart
              fundamental={detail.fundamental_freq}
              centroid={detail.spectral_centroid}
              bandwidth={detail.spectral_bandwidth}
              rolloff={detail.rolloff}
            />
            <MFCCChart mfcc={detail.mfcc ?? []} />

            {/* Piano keyboard */}
            {((detail.notes?.length ?? 0) > 0 || detail.root_note) && (
              <PianoKeyboard
                rootNote={detail.root_note}
                notes={detail.notes ?? []}
              />
            )}

            {/* Deep analysis */}
            {detail.deep_analysis_status && (
              <DeepAnalysisSection detail={detail} />
            )}

            {/* Musical context */}
            {detail.musical_record && (
              <>
                <MusicalRecordCard record={detail.musical_record} />
                {detail.compatibility && (
                  <>
                    <CompatibleKeysCard keys={detail.compatibility.keys} />
                    <ProgressionsCard
                      progressions={detail.compatibility.progressions}
                      sampleId={selectedId}
                    />
                  </>
                )}
                {detail.mood_profile && (
                  <MoodCard
                    primary={detail.mood_profile.primary}
                    supporting={detail.mood_profile.supporting}
                    transitions={detail.transition_suggestions ?? []}
                  />
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MetadataGrid({ detail }: { detail: SampleDetail }) {
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

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
      {chips.map(([label, value]) =>
        value != null && value !== "" ? (
          <div
            key={label}
            className="rounded border border-gray-200 bg-gray-50 px-2.5 py-1.5"
          >
            <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
              {label}
            </p>
            <p className="text-sm font-medium text-gray-800 truncate">
              {String(value)}
            </p>
          </div>
        ) : null,
      )}
    </div>
  );
}

function PianoKeyboard({
  rootNote,
  notes,
}: {
  rootNote: string | null;
  notes: string[];
}) {
  const noteSet = new Set(notes);

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Piano / Notes
      </h3>
      <div className="flex gap-0.5">
        {NOTE_ORDER.map((note) => {
          const isBlack = BLACK_KEYS.has(note);
          const isRoot = note === rootNote;
          const isActive = noteSet.has(note);
          return (
            <div
              key={note}
              className={`flex flex-col items-center justify-end rounded text-[10px] font-medium transition-colors ${
                isBlack
                  ? `w-7 h-14 ${isRoot ? "bg-teal-700 text-white" : isActive ? "bg-gray-700 text-white ring-1 ring-teal-400" : "bg-gray-800 text-gray-400"}`
                  : `w-9 h-16 border ${isRoot ? "bg-teal-500 text-white border-teal-600" : isActive ? "bg-teal-50 text-teal-800 border-teal-300" : "bg-white text-gray-500 border-gray-300"}`
              }`}
            >
              <span className="pb-1">{note}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DeepAnalysisSection({ detail }: { detail: SampleDetail }) {
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
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Deep Analysis
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        {chips.map(([label, value]) =>
          value != null && value !== "" ? (
            <div
              key={label}
              className="rounded border border-gray-200 bg-gray-50 px-2.5 py-1.5"
            >
              <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
                {label}
              </p>
              <p className="text-sm font-medium text-gray-800">{String(value)}</p>
            </div>
          ) : null,
        )}
      </div>
      {engines.length > 0 && (
        <p className="mt-2 text-xs text-gray-500">
          Engines: {engines.join(" · ")}
        </p>
      )}
      {(detail.deep_chords?.length ?? 0) > 0 && (
        <p className="mt-1 text-xs text-gray-500">
          Chords: {detail.deep_chords.slice(0, 12).join(", ")}
          {detail.deep_chords.length > 12 && ` +${detail.deep_chords.length - 12} more`}
        </p>
      )}
      {(detail.deep_note_events?.length ?? 0) > 0 && (
        <p className="mt-1 text-xs text-gray-500">
          Notes: {detail.deep_note_events.slice(0, 8).map((e) => e.note).join(", ")}
          {detail.deep_note_events.length > 8 && ` +${detail.deep_note_events.length - 8} more`}
        </p>
      )}
    </div>
  );
}

function MusicalRecordCard({ record }: { record: NonNullable<SampleDetail["musical_record"]> }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Musical Record
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3">
        <Chip label="Key" value={record.key} />
        <Chip label="Tonic" value={record.tonic} />
        <Chip label="Scale" value={record.scale} />
        <Chip label="BPM" value={record.bpm != null ? `${record.bpm.toFixed(1)}` : null} />
        <Chip label="Tuning" value={record.tuning != null ? `${record.tuning.toFixed(2)} Hz` : null} />
        <Chip label="Confidence" value={record.confidence != null ? record.confidence.toFixed(2) : null} />
      </div>
      {record.notes?.length > 0 && (
        <p className="mt-2 text-xs text-gray-500">
          Notes: {record.notes.join(" ")}
        </p>
      )}
    </div>
  );
}

function PanelHeader({
  name,
  detail,
  sampleId,
  onClose,
}: {
  name: string | undefined;
  detail: SampleDetail | undefined;
  sampleId: number;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const samples = useAppStore((s) => s.samples);
  const setSamples = useAppStore((s) => s.setSamples);
  const [reviewing, setReviewing] = useState(false);

  const isReviewed = detail?.reviewed ?? false;
  const isWritable = detail?.index_writable ?? false;
  const reasons = detail?.review_reasons ?? [];

  const handleReview = useCallback(async () => {
    setReviewing(true);
    try {
      await postReview(sampleId, !isReviewed);
      queryClient.invalidateQueries({ queryKey: ["sample-detail", sampleId] });
      setSamples(
        samples.map((s) =>
          s.id === sampleId ? { ...s, reviewed: !isReviewed } : s,
        ),
      );
    } catch (err) {
      console.error("Review failed:", err);
    } finally {
      setReviewing(false);
    }
  }, [sampleId, isReviewed, queryClient, samples, setSamples]);

  return (
    <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-widest text-gray-400">
            Now Playing
          </p>
          <h2 className="text-sm font-semibold text-gray-900 truncate">
            {name ?? "Loading..."}
          </h2>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-4">
          {detail && isWritable && (
            <button
              onClick={handleReview}
              disabled={reviewing}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors disabled:opacity-50 ${
                isReviewed
                  ? "border border-gray-300 text-gray-600 hover:bg-gray-100"
                  : "bg-teal-600 text-white hover:bg-teal-700"
              }`}
            >
              {reviewing
                ? "Saving..."
                : isReviewed
                  ? "Mark unreviewed"
                  : "Mark reviewed"}
            </button>
          )}
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 text-xl leading-none"
          >
            ✕
          </button>
        </div>
      </div>
      {reasons.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {reasons.map((r) => (
            <span
              key={r}
              className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-50 text-amber-700 border border-amber-200"
            >
              {r}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function CompatibleKeysCard({ keys }: { keys: CompatibleKey[] }) {
  if (keys.length === 0) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Compatible Keys
      </h3>
      <div className="space-y-2">
        {keys.map((k) => (
          <div
            key={k.label}
            className="rounded-lg border border-gray-200 bg-gray-50 p-3"
          >
            <div className="flex items-baseline gap-2">
              <span className="text-xs font-semibold text-gray-700">{k.label}</span>
              <span className="text-sm font-medium text-gray-900">{k.scale}</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {(k.diatonic_chords ?? k.chords ?? []).join(" / ")}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProgressionsCard({
  progressions,
  sampleId,
}: {
  progressions: Progression[];
  sampleId: number;
}) {
  if (progressions.length === 0) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Progressions to Try
      </h3>
      <div className="space-y-2">
        {progressions.map((p, i) => (
          <div
            key={p.name}
            className="rounded-lg border border-gray-200 bg-gray-50 p-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-gray-800">
                  {p.name}
                </span>
                <span className="ml-2 text-xs text-gray-500">{p.numerals}</span>
              </div>
              <a
                href={getMidiUrl(sampleId, i)}
                download
                className="px-2.5 py-1 text-xs font-medium rounded bg-teal-600 text-white hover:bg-teal-700 transition-colors"
              >
                MIDI
              </a>
            </div>
            <p className="text-xs text-gray-600 mt-1">
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

function MoodCard({
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
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Mood & Transitions
      </h3>
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
        <p className="text-sm text-gray-800">
          <span className="font-semibold">{primary}</span>
          {supporting.length > 0 && (
            <span className="text-gray-500">
              {" "}· {supporting.join(", ")}
            </span>
          )}
        </p>
        {transitions.length > 0 && (
          <div className="space-y-1">
            {transitions.map((t) => (
              <p key={t.label} className="text-xs text-gray-500">
                → <span className="font-medium text-gray-700">{t.label}</span>{" "}
                {t.why}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Chip({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  if (value == null || value === "") return null;
  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
        {label}
      </p>
      <p className="text-sm font-medium text-gray-800">{String(value)}</p>
    </div>
  );
}
