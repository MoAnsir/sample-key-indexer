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
    <div className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="chip-label tracking-widest">Now Playing</p>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
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
                  ? "border border-gray-300 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
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
            className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-xl leading-none"
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
