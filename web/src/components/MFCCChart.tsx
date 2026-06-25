import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import SectionLabel from "./ui/SectionLabel";

export default function MFCCChart({ mfcc }: { mfcc: number[] }) {
  if (!mfcc || mfcc.length === 0) return null;

  const data = mfcc.map((value, i) => ({
    name: `${i + 1}`,
    value: Math.round(value * 100) / 100,
  }));

  return (
    <div>
      <SectionLabel>MFCC Timbre Shape</SectionLabel>
      <div className="card">
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={data} margin={{ left: 10, right: 10 }}>
            <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--muted)" }} />
            <YAxis tick={{ fontSize: 10, fill: "var(--muted)" }} width={50} />
            <Tooltip contentStyle={{ fontSize: 12, padding: "4px 8px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} formatter={(value) => [Number(value).toFixed(2), "MFCC"]} />
            <Bar dataKey="value" radius={[2, 2, 0, 0]} barSize={20}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.value >= 0 ? "var(--accent)" : "#e85d5d"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
