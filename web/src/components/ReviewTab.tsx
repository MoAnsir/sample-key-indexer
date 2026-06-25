import { useAppStore } from "../store/useAppStore";
import { useReviewFiltering } from "../hooks/useReviewFiltering";
import PaginationBar from "./PaginationBar";
import type { Sample } from "../types/api";

const BADGE_ACTIVE = "bg-accent text-accent-ink";
const BADGE_INACTIVE = "border border-line bg-surface text-muted hover:border-accent";

export default function ReviewTab() {
  const samples = useAppStore((s) => s.samples);
  const setSelectedSampleId = useAppStore((s) => s.setSelectedSampleId);

  const review = useReviewFiltering(samples);
  const { state, allFlagged, filtered, pageRows, totalPages, start } = review;

  const paginationProps = {
    page: state.page,
    totalPages,
    pageSize: state.pageSize,
    showingFrom: filtered.length > 0 ? start + 1 : 0,
    showingTo: Math.min(start + state.pageSize, filtered.length),
    totalFiltered: filtered.length,
    totalAll: allFlagged.length,
    label: "flagged samples" as const,
    onPageChange: review.setPage,
    onPageSizeChange: review.setPageSize,
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="p-4 space-y-4 bg-surface border-b border-line flex-shrink-0">
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <StatCard label="Flagged" value={allFlagged.length.toLocaleString()} />
          <StatCard label="% of library" value={`${review.pct}%`} />
          <StatCard label="Reviewed" value={`${review.reviewedCount} / ${allFlagged.length}`} />
          <StatCard label="Remaining" value={(allFlagged.length - review.reviewedCount).toLocaleString()} />
          <StatCard label="Lowest confidence" value={review.lowestConf} />
        </div>

        {review.reasonCounts.length > 0 && (
          <FilterBadgeGroup
            label="Filter by reason"
            items={review.reasonCounts}
            activeValue={state.reasonFilter}
            onToggle={(v) => review.setReasonFilter(state.reasonFilter === v ? "" : v)}
            mono
          />
        )}

        {review.typeCounts.length > 0 && (
          <FilterBadgeGroup
            label="Filter by type"
            items={review.typeCounts}
            activeValue={state.typeFilter}
            onToggle={(v) => review.setTypeFilter(state.typeFilter === v ? "" : v)}
          />
        )}

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-1.5 text-xs text-muted font-sans cursor-pointer">
            <input
              type="checkbox"
              checked={state.includeReviewed}
              onChange={(e) => review.setIncludeReviewed(e.target.checked)}
            />
            Include reviewed
          </label>
          {review.hasFilters && (
            <button onClick={review.clearFilters} className="text-xs text-accent hover:underline">
              Clear filters
            </button>
          )}
        </div>
      </div>

      <PaginationBar position="top" {...paginationProps} />

      <div className="flex-1 overflow-auto">
        {pageRows.length === 0 ? (
          <div className="p-8 text-center text-faint font-sans">
            No samples match the current filters
          </div>
        ) : (
          <div className="divide-y divide-line">
            {pageRows.map((sample) => (
              <ReviewRow
                key={sample.id}
                sample={sample}
                onClick={() => setSelectedSampleId(sample.id)}
              />
            ))}
          </div>
        )}
      </div>

      <PaginationBar position="bottom" {...paginationProps} />
    </div>
  );
}

function FilterBadgeGroup({
  label,
  items,
  activeValue,
  onToggle,
  mono,
}: {
  label: string;
  items: [string, number][];
  activeValue: string;
  onToggle: (value: string) => void;
  mono?: boolean;
}) {
  return (
    <div>
      <h3 className="chip-label mb-1.5">{label}</h3>
      <div className="flex flex-wrap gap-1.5">
        {items.map(([value, count]) => (
          <button
            key={value}
            onClick={() => onToggle(value)}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded-chip text-xs font-sans transition-colors ${
              activeValue === value ? BADGE_ACTIVE : BADGE_INACTIVE
            }`}
          >
            <span className={mono ? "font-mono" : ""}>{value}</span>
            <span className="font-semibold">{count}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="chip-card">
      <p className="chip-label">{label}</p>
      <p className="text-lg font-display font-bold text-ink mt-0.5">{value}</p>
    </div>
  );
}

function ReviewRow({ sample, onClick }: { sample: Sample; onClick: () => void }) {
  const reasons = sample.review_reasons ?? [];
  return (
    <button
      onClick={onClick}
      className="w-full flex items-start gap-3 px-4 py-3 hover:bg-surface-2 text-left transition-colors"
    >
      <span
        className={`w-10 text-xs font-mono font-bold tabular-nums shrink-0 mt-0.5 ${
          (sample.confidence ?? 0) < 0.3
            ? "text-warn"
            : (sample.confidence ?? 0) < 0.6
              ? "text-warn/70"
              : "text-muted"
        }`}
      >
        {(sample.confidence ?? 0).toFixed(2)}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-sans font-medium text-ink truncate">{sample.name}</p>
        {reasons.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {reasons.map((r) => (
              <span
                key={r}
                className="inline-block px-1.5 py-0.5 rounded-chip text-[10px] font-mono bg-warn/15 text-warn border border-warn/30"
              >
                {r}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0 mt-0.5">
        <span className="text-xs text-faint font-sans">{sample.type}</span>
        <span className="text-xs text-faint font-mono">{sample.key ?? "—"}</span>
        {sample.reviewed && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-pill bg-good/15 text-good font-sans">
            Reviewed
          </span>
        )}
      </div>
    </button>
  );
}
