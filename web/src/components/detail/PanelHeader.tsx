import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { postReview } from "../../api/client";
import { useAppStore } from "../../store/useAppStore";
import type { SampleDetail } from "../../types/api";

interface PanelHeaderProps {
  name: string | undefined;
  detail: SampleDetail | undefined;
  sampleId: number;
  onClose: () => void;
}

export default function PanelHeader({ name, detail, sampleId, onClose }: PanelHeaderProps) {
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
    <div className="sticky top-0 z-10 bg-surface border-b border-line px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="chip-label tracking-widest">Now Playing</p>
          <h2 className="text-sm font-semibold text-ink truncate">
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
                  ? "border border-line text-muted hover:bg-surface-2 hover:bg-surface-2"
                  : "bg-accent text-white hover:opacity-90"
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
            className="text-faint hover:text-ink dark:hover:text-ink text-xl leading-none"
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
              className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-warn/10 text-warn border border-warn/30"
            >
              {r}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
