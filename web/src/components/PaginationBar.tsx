interface PaginationBarProps {
  page: number;
  totalPages: number;
  pageSize: number;
  showingFrom: number;
  showingTo: number;
  totalFiltered: number;
  totalAll: number;
  position: "top" | "bottom";
  label?: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

export default function PaginationBar({
  page,
  totalPages,
  pageSize,
  showingFrom,
  showingTo,
  totalFiltered,
  totalAll,
  position,
  label = "samples",
  onPageChange,
  onPageSizeChange,
}: PaginationBarProps) {
  return (
    <div
      className={`flex items-center justify-between px-4 py-3 bg-surface flex-shrink-0 ${
        position === "top" ? "border-b border-line" : "border-t border-line"
      }`}
    >
      <div className="text-sm text-muted font-sans">
        Showing{" "}
        <span className="font-semibold text-ink">
          {showingFrom.toLocaleString()}–{showingTo.toLocaleString()}
        </span>{" "}
        of{" "}
        <span className="font-semibold text-ink">
          {totalFiltered.toLocaleString()}
        </span>{" "}
        {label}
        {totalFiltered < totalAll && (
          <span className="text-faint">
            {" "}(filtered from {totalAll.toLocaleString()})
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {position === "top" && (
          <label className="text-xs text-muted font-sans">
            Rows
            <select
              className="ml-1.5 input-base h-8 text-sm"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
            >
              {[100, 250, 500, 1000].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          className="px-3 py-1.5 text-sm font-sans font-medium rounded-control border border-line text-ink bg-surface hover:bg-surface-2 disabled:opacity-30 transition-colors"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ← Previous
        </button>
        <span className="text-sm font-mono font-medium text-ink min-w-[100px] text-center">
          Page {page} of {totalPages}
        </span>
        <button
          className="px-3 py-1.5 text-sm font-sans font-medium rounded-control border border-line text-ink bg-surface hover:bg-surface-2 disabled:opacity-30 transition-colors"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next →
        </button>
      </div>
    </div>
  );
}
