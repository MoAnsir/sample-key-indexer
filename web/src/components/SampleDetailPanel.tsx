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
import ReviewDiagnostic from "./ReviewDiagnostic";
import ErrorBoundary from "./ui/ErrorBoundary";
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
          <div className="animate-spin h-8 w-8 border-4 border-teal-600 border-t-transparent rounded-full" />
          <p className="text-sm text-gray-400">Loading sample details...</p>
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
  return (
    <div className="p-6 space-y-6">
      <ReviewDiagnostic detail={detail} />

      <div id="section-audio">
        {detail.playback_status === "available" ? (
          <AudioPlayer sampleId={sampleId} autoPlay />
        ) : (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
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

      <div id="section-piano">
        {((detail.notes?.length ?? 0) > 0 || detail.root_note) && (
          <PianoKeyboard rootNote={detail.root_note} notes={detail.notes ?? []} />
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
