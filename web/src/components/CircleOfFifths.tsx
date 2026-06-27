import { CIRCLE_OF_FIFTHS, keyColor, parseKey, type Mode } from "../lib/key-color";
import { useAppStore } from "../store/useAppStore";

interface CircleOfFifthsProps {
  activeKey?: string | null;
  highlightedKeys?: string[];
  size?: number;
}

export default function CircleOfFifths({
  activeKey = null,
  highlightedKeys = [],
  size = 240,
}: CircleOfFifthsProps) {
  const isDark = useAppStore((s) => s.isDark);
  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 8;
  const innerR = outerR * 0.55;
  const labelR = outerR * 0.78;

  const { root: activeRoot } = parseKey(activeKey);
  const highlightSet = new Set(
    highlightedKeys.map((k) => parseKey(k).root).filter(Boolean),
  );

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      className="mx-auto"
    >
      {CIRCLE_OF_FIFTHS.map((note, i) => {
        const startAngle = (i / 12) * 360 - 90 - 15;
        const endAngle = startAngle + 30;
        const isActive = note === activeRoot;
        const isHighlighted = highlightSet.has(note);
        const mode: Mode = "major";
        const kc = keyColor(note, mode, isDark);

        const startRad = (startAngle * Math.PI) / 180;
        const endRad = (endAngle * Math.PI) / 180;

        const outerX1 = cx + outerR * Math.cos(startRad);
        const outerY1 = cy + outerR * Math.sin(startRad);
        const outerX2 = cx + outerR * Math.cos(endRad);
        const outerY2 = cy + outerR * Math.sin(endRad);
        const innerX1 = cx + innerR * Math.cos(endRad);
        const innerY1 = cy + innerR * Math.sin(endRad);
        const innerX2 = cx + innerR * Math.cos(startRad);
        const innerY2 = cy + innerR * Math.sin(startRad);

        const path = [
          `M ${outerX1} ${outerY1}`,
          `A ${outerR} ${outerR} 0 0 1 ${outerX2} ${outerY2}`,
          `L ${innerX1} ${innerY1}`,
          `A ${innerR} ${innerR} 0 0 0 ${innerX2} ${innerY2}`,
          "Z",
        ].join(" ");

        const midAngle = ((startAngle + endAngle) / 2) * (Math.PI / 180);
        const labelX = cx + labelR * Math.cos(midAngle);
        const labelY = cy + labelR * Math.sin(midAngle);

        return (
          <g key={note}>
            <path
              d={path}
              fill={isActive ? kc.solid : isHighlighted ? kc.bg : isDark ? "#2a2a2a" : "#f0f0f0"}
              stroke={isActive || isHighlighted ? kc.border : isDark ? "#3a3a3a" : "#e0e0e0"}
              strokeWidth={isActive ? 2 : 1}
              opacity={isActive || isHighlighted ? 1 : 0.6}
            />
            <text
              x={labelX}
              y={labelY}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={isActive ? 13 : 11}
              fontWeight={isActive ? 700 : 500}
              fontFamily="'Space Grotesk', system-ui, sans-serif"
              fill={
                isActive
                  ? "white"
                  : isHighlighted
                    ? kc.ink
                    : isDark
                      ? "#999"
                      : "#666"
              }
            >
              {note}
            </text>
          </g>
        );
      })}

      {/* Center label */}
      {activeKey && (
        <>
          <text
            x={cx}
            y={cy - 6}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={16}
            fontWeight={700}
            fontFamily="'Space Grotesk', system-ui, sans-serif"
            fill={isDark ? "#e0e0e0" : "#333"}
          >
            {activeKey.replace("_", " ")}
          </text>
          <text
            x={cx}
            y={cy + 12}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={10}
            fill={isDark ? "#888" : "#999"}
            fontFamily="system-ui, sans-serif"
          >
            detected key
          </text>
        </>
      )}
    </svg>
  );
}
