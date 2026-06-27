import { useQuery } from "@tanstack/react-query";
import { fetchSampleDetail } from "../api/client";
import { useAppStore } from "../store/useAppStore";
import PanelShell from "./detail/PanelShell";
import PanelHeader from "./detail/PanelHeader";
import MetadataGrid from "./detail/MetadataGrid";
import PianoKeyboard from "./detail/PianoKeyboard";
import DeepAnalysisSection from "./detail/DeepAnalysisSection";
import { MusicalRecordCard, CompatibleKeysCard, ProgressionsCard, MoodCard } from "./detail/MusicalContext";
import AudioPlayer from "./AudioPlayer";
import FrequencyChart from "./FrequencyChart";
import MFCCChart from "./MFCCChart";
import CircleOfFifths from "./CircleOfFifths";
import ReviewDiagnostic from "./ReviewDiagnostic";
import ErrorBoundary from "./ui/ErrorBoundary";
import InfoTooltip from "./ui/InfoTooltip";
import { keyColor, parseKey } from "../lib/key-color";
import type { SampleDetail } from "../types/api";

export default function SampleDetailPanel() {
  const selectedId = useAppStore((s) => s.selectedSampleId);
  const setSelectedSampleId = useAppStore((s) => s.setSelectedSampleId);

  const { data: detail, isLoading, error } = useQuery<SampleDetail>({
    queryKey: ["sample-detail", selectedId],
    queryFn: () => fetchSampleDetail(selectedId!),
    enabled: selectedId != null,
  });

  if (selectedId == null) return null;

  return (
    <PanelShell open={selectedId != null} onClose={() => setSelectedSampleId(null)}>
      <PanelHeader
        name={detail?.name}
        detail={detail}
        sampleId={selectedId}
        onClose={() => setSelectedSampleId(null)}
      />

      {error ? (
        <div className="p-6">
          <p className="text-red-600">Error loading sample: {String(error)}</p>
        </div>
      ) : isLoading || !detail ? (
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" />
          <p className="text-sm text-faint">Loading sample details...</p>
        </div>
      ) : (
        <ErrorBoundary>
          <SampleContent detail={detail} sampleId={selectedId} />
        </ErrorBoundary>
      )}
    </PanelShell>
  );
}

function SampleContent({ detail, sampleId }: { detail: SampleDetail; sampleId: number }) {
  const isDark = useAppStore((s) => s.isDark);
  const { root, mode } = parseKey(detail.key ?? null);
  const kc = keyColor(root, mode, isDark);

  // Pick a different note for the "active note" example
  const activeNote = detail.notes?.find((n) => n !== detail.root_note) ?? detail.root_note;
  const activeKc = keyColor(activeNote, "major", isDark);
  const wheelGrey = isDark ? "#2a2a2a" : "#f0f0f0";

  return (
    <div className="p-6 space-y-6">
      <ReviewDiagnostic detail={detail} />

      <div id="section-audio">
        {detail.playback_status === "available" ? (
          <AudioPlayer sampleId={sampleId} autoPlay />
        ) : (
          <div className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">
            Audio unavailable — source media not mounted
          </div>
        )}
      </div>

      <div id="section-metadata">
        <MetadataGrid detail={detail} />
      </div>

      <div id="section-frequency">
        <FrequencyChart
          fundamental={detail.fundamental_freq}
          centroid={detail.spectral_centroid}
          bandwidth={detail.spectral_bandwidth}
          rolloff={detail.rolloff}
        />
      </div>

      <div id="section-mfcc">
        <MFCCChart mfcc={detail.mfcc ?? []} />
      </div>

      {/* Circle of Fifths + Piano side by side */}
      <div id="section-piano" className="grid gap-4 lg:grid-cols-2">
        {detail.key && (
          <div>
            <h3 className="section-label flex items-center gap-1.5">
              Circle of Fifths
              <InfoTooltip lines={[
                "Each wedge is a musical key, arranged by the circle of fifths.",
                { text: `Solid color = the detected key (${detail.key?.replace("_", " ") ?? "none"}).`, color: kc.solid, border: kc.border },
                { text: "Lighter wedges = compatible keys that mix well (relative, dominant, subdominant, parallel).", color: kc.bg, border: kc.border },
                { text: "Grey = unrelated keys.", color: wheelGrey, border: isDark ? "#3a3a3a" : "#ddd" },
                "Nearby wedges share similar hue because harmonically related keys sit next to each other.",
              ]} />
            </h3>
            <CircleOfFifths
              activeKey={detail.key}
              highlightedKeys={
                detail.compatibility?.keys.map((k) => k.key) ?? []
              }
              size={220}
            />
          </div>
        )}
        {((detail.notes?.length ?? 0) > 0 || detail.root_note) && (
          <div>
            <h3 className="section-label flex items-center gap-1.5">
              Root & Detected Notes
              <InfoTooltip lines={[
                "Shows which notes were detected in this sample.",
                { text: `Solid colored key = the root note (${detail.root_note ?? "none"}).`, color: kc.solid, border: kc.border },
                { text: "Tinted keys = other detected notes.", color: activeKc.bg, border: activeKc.border },
                { text: "Plain keys = not detected in this sample.", color: isDark ? "#2a2620" : "#e8e8e8", border: isDark ? "#3a3a3a" : "#ccc" },
                "Colors match the circle of fifths — same hue = same key family.",
              ]} />
            </h3>
            <PianoKeyboard rootNote={detail.root_note} notes={detail.notes ?? []} showLabel={false} />
          </div>
        )}
      </div>

      <div id="section-deep-analysis">
        {detail.deep_analysis_status && <DeepAnalysisSection detail={detail} />}
      </div>

      {detail.musical_record && (
        <>
          <div id="section-musical-record">
            <MusicalRecordCard record={detail.musical_record} />
          </div>
          {detail.compatibility && (
            <>
              <div id="section-compatible-keys">
                <CompatibleKeysCard keys={detail.compatibility.keys} />
              </div>
              <div id="section-progressions">
                <ProgressionsCard
                  progressions={detail.compatibility.progressions}
                  sampleId={sampleId}
                />
              </div>
            </>
          )}
          {detail.mood_profile && (
            <div id="section-mood">
              <MoodCard
                primary={detail.mood_profile.primary}
                supporting={detail.mood_profile.supporting}
                transitions={detail.transition_suggestions ?? []}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
