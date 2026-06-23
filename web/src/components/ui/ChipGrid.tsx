interface ChipGridProps {
  chips: [string, string | number | null | undefined][];
}

export default function ChipGrid({ chips }: ChipGridProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
      {chips.map(([label, value]) =>
        value != null && value !== "" ? (
          <div key={label} className="chip-card">
            <p className="chip-label">{label}</p>
            <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
              {String(value)}
            </p>
          </div>
        ) : null,
      )}
    </div>
  );
}
