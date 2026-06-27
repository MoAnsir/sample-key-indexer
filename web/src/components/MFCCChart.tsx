import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface MFCCChartProps {
  mfcc: number[];
}

export default function MFCCChart({ mfcc }: MFCCChartProps) {
  if (!mfcc || mfcc.length === 0) return null;

  const data = mfcc.map((value, i) => ({
    name: `${i + 1}`,
    value: Math.round(value * 100) / 100,
  }));

  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
        MFCC Timbre Shape
      </h3>
      <div className="rounded-lg border border-line bg-surface p-3">
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={data} margin={{ left: 10, right: 10 }}>
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} width={50} />
            <Tooltip contentStyle={{ fontSize: 12, padding: "4px 8px" }} formatter={(value) => [Number(value).toFixed(2), "MFCC"]} />
            <Bar dataKey="value" radius={[2, 2, 0, 0]} barSize={20}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.value >= 0 ? "#0d9488" : "#e85d5d"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
