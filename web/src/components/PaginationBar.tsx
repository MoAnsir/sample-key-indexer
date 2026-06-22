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
      className={`flex items-center justify-between px-4 py-3 bg-white flex-shrink-0 ${
        position === "top" ? "border-b border-gray-200" : "border-t border-gray-200"
      }`}
    >
      <div className="text-sm text-gray-600">
        Showing{" "}
        <span className="font-semibold text-gray-900">
          {showingFrom.toLocaleString()}–{showingTo.toLocaleString()}
        </span>{" "}
        of{" "}
        <span className="font-semibold text-gray-900">
          {totalFiltered.toLocaleString()}
        </span>{" "}
        {label}
        {totalFiltered < totalAll && (
          <span className="text-gray-400">
            {" "}(filtered from {totalAll.toLocaleString()})
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {position === "top" && (
          <label className="text-xs text-gray-500">
            Rows
            <select
              className="ml-1.5 input-base"
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
          className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ← Previous
        </button>
        <span className="text-sm font-medium text-gray-700 min-w-[100px] text-center">
          Page {page} of {totalPages}
        </span>
        <button
          className="px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-100 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next →
        </button>
      </div>
    </div>
  );
}
