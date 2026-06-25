import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import SectionLabel from "./ui/SectionLabel";

const COLORS = ["var(--accent)", "#e85d5d", "#d4a843", "var(--good)"];

interface FrequencyChartProps {
  fundamental: number | null;
  centroid: number | null;
  bandwidth: number | null;
  rolloff: number | null;
}

export default function FrequencyChart({ fundamental, centroid, bandwidth, rolloff }: FrequencyChartProps) {
  const data = [
    { name: "Fundamental", value: fundamental },
    { name: "Centroid", value: centroid },
    { name: "Bandwidth", value: bandwidth },
    { name: "Rolloff", value: rolloff },
  ].filter((d) => d.value != null);

  if (data.length === 0) return null;

  return (
    <div>
      <SectionLabel>Frequency Features</SectionLabel>
      <div className="card">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} layout="vertical" margin={{ left: 80, right: 40 }}>
            <XAxis type="number" tick={{ fontSize: 10, fill: "var(--muted)" }} tickFormatter={(v) => `${v} Hz`} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "var(--ink)" }} width={75} />
            <Tooltip contentStyle={{ fontSize: 12, padding: "4px 8px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} formatter={(value) => [`${Math.round(Number(value))} Hz`]} />
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
