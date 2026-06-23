interface ChipProps {
  label: string;
  value: string | number | null | undefined;
}

export default function Chip({ label, value }: ChipProps) {
  if (value == null || value === "") return null;
  return (
    <div>
      <p className="chip-label">{label}</p>
      <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
        {String(value)}
      </p>
    </div>
  );
}
