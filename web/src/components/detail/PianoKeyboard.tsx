import SectionLabel from "../ui/SectionLabel";

const NOTE_ORDER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const BLACK_KEYS = new Set(["C#", "D#", "F#", "G#", "A#"]);

interface PianoKeyboardProps {
  rootNote: string | null;
  notes: string[];
}

export default function PianoKeyboard({ rootNote, notes }: PianoKeyboardProps) {
  const noteSet = new Set(notes);

  return (
    <div>
      <SectionLabel>Piano / Notes</SectionLabel>
      <div className="flex gap-0.5">
        {NOTE_ORDER.map((note) => {
          const isBlack = BLACK_KEYS.has(note);
          const isRoot = note === rootNote;
          const isActive = noteSet.has(note);
          return (
            <div
              key={note}
              className={`flex flex-col items-center justify-end rounded text-[10px] font-medium transition-colors ${
                isBlack
                  ? `w-7 h-14 ${isRoot ? "bg-teal-700 text-white" : isActive ? "bg-gray-700 text-white ring-1 ring-teal-400" : "bg-gray-800 text-gray-400"}`
                  : `w-9 h-16 border ${isRoot ? "bg-teal-500 text-white border-teal-600" : isActive ? "bg-teal-50 dark:bg-teal-900 text-teal-800 dark:text-teal-200 border-teal-300" : "bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 border-gray-300 dark:border-gray-600"}`
              }`}
            >
              <span className="pb-1">{note}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
