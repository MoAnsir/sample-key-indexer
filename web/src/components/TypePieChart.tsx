import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { TypeStat } from "../types/api";

const COLORS = [
  "#0d9488", "#e85d5d", "#d4a843", "#4a9e6e", "#3b82c4", "#d46a9f",
  "#7c5cbf", "#c4703b", "#5c8f8f", "#8b6e4e", "#6b8e23", "#cd5c5c",
  "#4682b4", "#9370db", "#20b2aa", "#f4a460",
];

export default function TypePieChart({ stats, total }: { stats: TypeStat[]; total: number }) {
  if (stats.length === 0) return null;

  return (
    <div className="flex flex-col items-center">
      <h3 className="section-label">Type Share</h3>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={stats}
            dataKey="count"
            nameKey="type"
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={90}
            paddingAngle={1}
            strokeWidth={0}
            activeShape={false}
            style={{ outline: "none", cursor: "pointer" }}
          >
            {stats.map((_entry, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ fontSize: 12, padding: "4px 8px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }}
            formatter={(value, name) => [
              `${Number(value).toLocaleString()} (${((Number(value) / total) * 100).toFixed(1)}%)`,
              String(name),
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
      <p className="text-center -mt-4 mb-2">
        <span className="text-xl font-display font-bold text-ink">{total.toLocaleString()}</span>
        <span className="text-xs text-faint ml-1 font-sans">samples</span>
      </p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 justify-center mt-1">
        {stats.slice(0, 10).map((stat, i) => (
          <div key={stat.type} className="flex items-center gap-1 text-[10px] text-muted font-sans">
            <span
              className="w-2 h-2 rounded-full inline-block"
              style={{ backgroundColor: COLORS[i % COLORS.length] }}
            />
            {stat.type} · {stat.count.toLocaleString()}
          </div>
        ))}
      </div>
    </div>
  );
}
