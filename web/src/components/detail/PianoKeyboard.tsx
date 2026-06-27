import SectionLabel from "../ui/SectionLabel";
import { keyColor } from "../../lib/key-color";
import { useAppStore } from "../../store/useAppStore";

const NOTE_ORDER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const BLACK_KEYS = new Set(["C#", "D#", "F#", "G#", "A#"]);

interface PianoKeyboardProps {
  rootNote: string | null;
  notes: string[];
  showLabel?: boolean;
}

export default function PianoKeyboard({ rootNote, notes, showLabel = true }: PianoKeyboardProps) {
  const noteSet = new Set(notes);
  const isDark = useAppStore((s) => s.isDark);

  return (
    <div>
      {showLabel && <SectionLabel>Root & Detected Notes</SectionLabel>}
      <div className="flex gap-0.5">
        {NOTE_ORDER.map((note) => {
          const isBlack = BLACK_KEYS.has(note);
          const isRoot = note === rootNote;
          const isActive = noteSet.has(note);
          const kc = keyColor(isRoot || isActive ? note : null, "major", isDark);

          if (isRoot) {
            return (
              <div
                key={note}
                className={`flex flex-col items-center justify-end rounded text-[10px] font-semibold ${isBlack ? "w-7 h-14" : "w-9 h-16"}`}
                style={{ background: kc.solid, color: "white" }}
              >
                <span className="pb-1">{note}</span>
              </div>
            );
          }

          if (isActive) {
            return (
              <div
                key={note}
                className={`flex flex-col items-center justify-end rounded text-[10px] font-medium ${isBlack ? "w-7 h-14" : "w-9 h-16"}`}
                style={{ background: kc.bg, color: kc.ink, border: `1px solid ${kc.border}` }}
              >
                <span className="pb-1">{note}</span>
              </div>
            );
          }

          return (
            <div
              key={note}
              className={`flex flex-col items-center justify-end rounded text-[10px] font-medium transition-colors ${
                isBlack
                  ? "w-7 h-14"
                  : "w-9 h-16 border border-line"
              }`}
              style={{
                background: isBlack ? "var(--kbd-black)" : "var(--kbd-white)",
                color: "var(--faint)",
              }}
            >
              <span className="pb-1">{note}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
