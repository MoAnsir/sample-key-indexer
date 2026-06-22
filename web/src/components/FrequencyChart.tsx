import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const COLORS = ["#0d9488", "#e85d5d", "#d4a843", "#4a9e6e"];

interface FrequencyChartProps {
  fundamental: number | null;
  centroid: number | null;
  bandwidth: number | null;
  rolloff: number | null;
}

export default function FrequencyChart({
  fundamental,
  centroid,
  bandwidth,
  rolloff,
}: FrequencyChartProps) {
  const data = [
    { name: "Fundamental", value: fundamental, unit: "Hz" },
    { name: "Centroid", value: centroid, unit: "Hz" },
    { name: "Bandwidth", value: bandwidth, unit: "Hz" },
    { name: "Rolloff", value: rolloff, unit: "Hz" },
  ].filter((d) => d.value != null);

  if (data.length === 0) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        Frequency Features
      </h3>
      <div className="rounded-lg border border-gray-200 bg-white p-3">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} layout="vertical" margin={{ left: 80, right: 40 }}>
            <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={(v) => `${v} Hz`} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={75} />
            <Tooltip contentStyle={{ fontSize: 12, padding: "4px 8px" }} formatter={(value) => [`${Math.round(Number(value))} Hz`]} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={18}>
              {data.map((_entry, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
