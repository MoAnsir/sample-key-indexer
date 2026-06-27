import { useMemo } from "react";
import { keyColor, parseKey } from "../lib/key-color";
import { useAppStore } from "../store/useAppStore";
import InfoTooltip from "./ui/InfoTooltip";
import type { Sample } from "../types/api";

interface KeyDistributionProps {
  samples: Sample[];
  maxKeys?: number;
}

export default function KeyDistribution({ samples, maxKeys = 10 }: KeyDistributionProps) {
  const isDark = useAppStore((s) => s.isDark);

  const keyCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of samples) {
      if (s.key) {
        counts.set(s.key, (counts.get(s.key) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxKeys);
  }, [samples, maxKeys]);

  if (keyCounts.length === 0) return null;

  const maxCount = keyCounts[0][1];

  return (
    <div className="card">
      <h2 className="section-label flex items-center gap-1.5">
        Keys in Your Library
        <InfoTooltip lines={[
          "Shows the most common keys across all loaded samples.",
          "Each bar's color matches the key's position on the circle of fifths.",
          "Samples in the same key share the same color throughout the app.",
        ]} />
      </h2>
      <div className="space-y-2">
        {keyCounts.map(([key, count]) => {
          const { root, mode } = parseKey(key);
          const kc = keyColor(root, mode, isDark);
          const pct = (count / maxCount) * 100;

          return (
            <div key={key} className="flex items-center gap-3">
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ background: kc.solid }}
              />
              <span className="w-20 text-sm font-semibold text-ink shrink-0">
                {key.replace("_", " ")}
              </span>
              <div className="flex-1 h-[6px] rounded-full overflow-hidden bg-surface-2 ">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, background: kc.solid }}
                />
              </div>
              <span className="w-14 text-xs font-mono text-muted tabular-nums text-right shrink-0">
                {count.toLocaleString()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
