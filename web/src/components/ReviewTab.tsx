import { useMemo, useState } from "react";
import { useAppStore } from "../store/useAppStore";
import type { Sample } from "../types/api";

export default function ReviewTab() {
  const samples = useAppStore((s) => s.samples);
  const setSelectedSampleId = useAppStore((s) => s.setSelectedSampleId);
  const [includeReviewed, setIncludeReviewed] = useState(false);

  const flagged = useMemo(() => {
    let list = samples.filter((s) => s.needs_review);
    if (!includeReviewed) {
      list = list.filter((s) => !s.reviewed);
    }
    return list.sort((a, b) => (a.confidence ?? 0) - (b.confidence ?? 0));
  }, [samples, includeReviewed]);

  const totalFlagged = samples.filter((s) => s.needs_review).length;
  const reviewedCount = samples.filter((s) => s.needs_review && s.reviewed).length;
  const pct = samples.length > 0 ? ((totalFlagged / samples.length) * 100).toFixed(1) : "0";
  const lowestConf = flagged.length > 0 ? (flagged[0].confidence ?? 0).toFixed(2) : "—";

  const reasonCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of flagged) {
      for (const r of s.review_reasons ?? []) {
        counts.set(r, (counts.get(r) ?? 0) + 1);
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [flagged]);

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of flagged) {
      const t = s.type ?? "Unknown";
      counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [flagged]);

  return (
    <div className="p-6 space-y-6 overflow-auto">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Flagged for review" value={totalFlagged.toLocaleString()} />
        <StatCard label="% of library" value={`${pct}%`} />
        <StatCard label="Reviewed" value={`${reviewedCount} / ${totalFlagged}`} />
        <StatCard label="Lowest confidence" value={lowestConf} />
      </div>

      {/* Include reviewed toggle */}
      <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
        <input
          type="checkbox"
          checked={includeReviewed}
          onChange={(e) => setIncludeReviewed(e.target.checked)}
        />
        Include already reviewed
      </label>

      {/* Reason breakdown */}
      {reasonCounts.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
            Review Reasons
          </h3>
          <div className="space-y-1.5">
            {reasonCounts.map(([reason, count]) => (
              <div key={reason} className="flex items-center gap-3">
                <span className="flex-1 text-sm text-gray-700 font-mono">{reason}</span>
                <span className="text-sm text-gray-500 tabular-nums">{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Type breakdown */}
      {typeCounts.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
            Flagged by Type
          </h3>
          <div className="flex flex-wrap gap-2">
            {typeCounts.map(([type, count]) => (
              <span
                key={type}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-gray-200 bg-gray-50 text-xs text-gray-700"
              >
                {type}
                <span className="font-semibold text-gray-900">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Lowest confidence samples */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
          Lowest Confidence ({Math.min(flagged.length, 50)} of {flagged.length.toLocaleString()})
        </h3>
        {flagged.length === 0 ? (
          <p className="text-sm text-gray-400">No samples flagged for review</p>
        ) : (
          <div className="space-y-1">
            {flagged.slice(0, 50).map((sample) => (
              <ReviewRow
                key={sample.id}
                sample={sample}
                onClick={() => setSelectedSampleId(sample.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <p className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
        {label}
      </p>
      <p className="text-lg font-bold text-gray-900 mt-0.5">{value}</p>
    </div>
  );
}

function ReviewRow({
  sample,
  onClick,
}: {
  sample: Sample;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2 rounded hover:bg-teal-50 text-left transition-colors"
    >
      <span className="w-12 text-xs font-mono text-gray-500 tabular-nums shrink-0">
        {(sample.confidence ?? 0).toFixed(2)}
      </span>
      <span className="flex-1 text-sm text-gray-800 truncate">{sample.name}</span>
      <span className="text-xs text-gray-400 shrink-0">{sample.type}</span>
      <span className="text-xs text-gray-400 shrink-0">{sample.key ?? "—"}</span>
      {sample.reviewed && (
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-teal-100 text-teal-700 shrink-0">
          Reviewed
        </span>
      )}
    </button>
  );
}
