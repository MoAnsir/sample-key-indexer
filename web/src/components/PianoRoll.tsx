import { useCallback, useMemo, useRef, useState } from "react";
import {
  addNote,
  buildRows,
  eraseNote,
  moveNote,
  resizeNote,
  setVelocity,
  duplicateNotes,
  transposeNotes,
  TC_DIVISIONS,
  type RollNote,
  type SnapMode,
} from "../lib/piano-roll";

export type Tool = "pencil" | "eraser" | "select";

interface PianoRollProps {
  tonic: string;
  mode: string;
  bars: number;
  beatsPerBar: number;
  notes: RollNote[];
  onChange: (notes: RollNote[]) => void;
}

const ROW_HEIGHT = 18;
const KEY_WIDTH = 44;
const BEAT_WIDTH = 48;
const VELOCITY_LANE_HEIGHT = 56;

export default function PianoRoll({
  tonic,
  mode,
  bars,
  beatsPerBar,
  notes,
  onChange,
}: PianoRollProps) {
  const [tool, setTool] = useState<Tool>("pencil");
  const [chromatic, setChromatic] = useState(false);
  const [divisionIndex, setDivisionIndex] = useState(3); // 1/16
  const [snapMode, setSnapMode] = useState<SnapMode>("absolute");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [octaveLow, setOctaveLow] = useState(1); // C1
  const gridRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    id: number;
    kind: "move" | "resize";
    offsetBeats: number;
  } | null>(null);

  const totalBeats = bars * beatsPerBar;
  const division = TC_DIVISIONS[divisionIndex].beats;
  const lowMidi = (octaveLow + 1) * 12; // C(octaveLow)
  const highMidi = lowMidi + 35; // three octaves
  const rows = useMemo(
    () => buildRows(tonic, mode, lowMidi, highMidi, chromatic),
    [tonic, mode, lowMidi, highMidi, chromatic],
  );
  const rowIndexByMidi = useMemo(() => {
    const map = new Map<number, number>();
    rows.forEach((row, index) => map.set(row.midi, index));
    return map;
  }, [rows]);

  const gridWidth = totalBeats * BEAT_WIDTH;
  const gridHeight = rows.length * ROW_HEIGHT;

  const beatFromX = useCallback((x: number) => Math.max(0, Math.min(totalBeats, x / BEAT_WIDTH)), [totalBeats]);

  const handleGridClick = useCallback(
    (event: React.MouseEvent) => {
      if (dragRef.current) return;
      const rect = gridRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const rowIndex = Math.floor(y / ROW_HEIGHT);
      const row = rows[rowIndex];
      if (!row) return;
      if (tool === "pencil") {
        onChange(addNote(notes, row.midi, beatFromX(x), division, snapMode, totalBeats));
      }
    },
    [tool, rows, notes, division, snapMode, totalBeats, beatFromX, onChange],
  );

  const handleNoteClick = useCallback(
    (event: React.MouseEvent, note: RollNote) => {
      event.stopPropagation();
      if (tool === "eraser") {
        onChange(eraseNote(notes, note.id));
        setSelected((prev) => {
          const next = new Set(prev);
          next.delete(note.id);
          return next;
        });
        return;
      }
      // pencil & select tools: click selects (shift adds to selection)
      setSelected((prev) => {
        if (event.shiftKey) {
          const next = new Set(prev);
          if (next.has(note.id)) next.delete(note.id);
          else next.add(note.id);
          return next;
        }
        return new Set([note.id]);
      });
    },
    [tool, notes, onChange],
  );

  const handleNoteDoubleClick = useCallback(
    (event: React.MouseEvent, note: RollNote) => {
      event.stopPropagation();
      // MPC pencil: double-tap erases
      onChange(eraseNote(notes, note.id));
    },
    [notes, onChange],
  );

  const handleNotePointerDown = useCallback(
    (event: React.PointerEvent, note: RollNote, kind: "move" | "resize") => {
      if (tool === "eraser") return;
      event.stopPropagation();
      const rect = gridRef.current?.getBoundingClientRect();
      if (!rect) return;
      const beat = beatFromX(event.clientX - rect.left);
      dragRef.current = { id: note.id, kind, offsetBeats: beat - note.start };
      (event.target as Element).setPointerCapture?.(event.pointerId);
    },
    [tool, beatFromX],
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const rect = gridRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const beat = beatFromX(x);
      if (drag.kind === "move") {
        const rowIndex = Math.min(rows.length - 1, Math.max(0, Math.floor(y / ROW_HEIGHT)));
        const row = rows[rowIndex];
        if (!row) return;
        onChange(
          moveNote(notes, drag.id, row.midi, beat - drag.offsetBeats, division, snapMode, totalBeats),
        );
      } else {
        const note = notes.find((n) => n.id === drag.id);
        if (!note) return;
        onChange(resizeNote(notes, drag.id, beat - note.start, division, snapMode, totalBeats));
      }
    },
    [rows, notes, division, snapMode, totalBeats, beatFromX, onChange],
  );

  const handlePointerUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  const handleVelocityChange = useCallback(
    (note: RollNote, velocity: number) => {
      onChange(setVelocity(notes, note.id, velocity));
    },
    [notes, onChange],
  );

  const handleTranspose = useCallback(
    (semitones: number) => {
      if (selected.size === 0) return;
      onChange(transposeNotes(notes, selected, semitones));
    },
    [notes, selected, onChange],
  );

  const handleDuplicate = useCallback(() => {
    if (selected.size === 0) return;
    onChange(duplicateNotes(notes, selected, totalBeats));
  }, [notes, selected, totalBeats, onChange]);

  const handleClear = useCallback(() => {
    onChange([]);
    setSelected(new Set());
  }, [onChange]);

  return (
    <div data-testid="piano-roll">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <div className="flex gap-0.5 bg-surface-2 border border-line rounded-control p-0.5">
          {(
            [
              ["pencil", "✏ Pencil"],
              ["eraser", "⌫ Eraser"],
              ["select", "▭ Select"],
            ] as [Tool, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setTool(value)}
              aria-pressed={tool === value}
              className={`px-2 py-1 text-xs font-medium rounded-chip transition-colors ${
                tool === value ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-1 text-xs text-muted">
          T.C.
          <select
            value={divisionIndex}
            onChange={(e) => setDivisionIndex(Number(e.target.value))}
            className="rounded-control border border-line bg-surface-2 px-1.5 py-1 text-xs text-ink"
          >
            {TC_DIVISIONS.map((d, i) => (
              <option key={d.label} value={i}>
                {d.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-1 text-xs text-muted">
          Snap
          <select
            value={snapMode}
            onChange={(e) => setSnapMode(e.target.value as SnapMode)}
            className="rounded-control border border-line bg-surface-2 px-1.5 py-1 text-xs text-ink"
          >
            <option value="absolute">Absolute</option>
            <option value="relative">Relative</option>
            <option value="off">Off</option>
          </select>
        </label>

        <button
          onClick={() => setChromatic((c) => !c)}
          aria-pressed={chromatic}
          className={`px-2 py-1 text-xs rounded-control border ${
            chromatic ? "border-accent text-accent" : "border-line text-muted hover:text-ink"
          }`}
        >
          Chromatic
        </button>

        <div className="flex items-center gap-1 text-xs text-muted">
          Octave
          <button
            onClick={() => setOctaveLow((o) => Math.max(-1, o - 1))}
            className="px-1.5 py-1 rounded-control border border-line text-muted hover:text-ink"
            aria-label="Octave down"
          >
            −
          </button>
          <span className="text-ink font-mono">C{octaveLow}</span>
          <button
            onClick={() => setOctaveLow((o) => Math.min(7, o + 1))}
            className="px-1.5 py-1 rounded-control border border-line text-muted hover:text-ink"
            aria-label="Octave up"
          >
            +
          </button>
        </div>

        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => handleTranspose(-1)}
            disabled={selected.size === 0}
            className="px-2 py-1 text-xs rounded-control border border-line text-muted hover:text-ink disabled:opacity-40"
          >
            Transpose −1
          </button>
          <button
            onClick={() => handleTranspose(1)}
            disabled={selected.size === 0}
            className="px-2 py-1 text-xs rounded-control border border-line text-muted hover:text-ink disabled:opacity-40"
          >
            +1
          </button>
          <button
            onClick={handleDuplicate}
            disabled={selected.size === 0}
            className="px-2 py-1 text-xs rounded-control border border-line text-muted hover:text-ink disabled:opacity-40"
          >
            Duplicate
          </button>
          <button
            onClick={handleClear}
            disabled={notes.length === 0}
            className="px-2 py-1 text-xs rounded-control border border-line text-warn hover:opacity-80 disabled:opacity-40"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Grid */}
      <div className="overflow-auto border border-line rounded-control bg-surface-2" style={{ maxHeight: 340 }}>
        <div className="flex" style={{ width: KEY_WIDTH + gridWidth }}>
          {/* Key column */}
          <div className="flex-shrink-0 sticky left-0 z-10" style={{ width: KEY_WIDTH }}>
            {rows.map((row) => (
              <div
                key={row.midi}
                data-testid={`key-${row.name}`}
                className={`flex items-center justify-end pr-1 text-[9px] font-mono border-b border-r border-line ${
                  row.isRoot
                    ? "bg-red-500/20 text-red-400 font-bold"
                    : row.inScale
                      ? "bg-surface text-muted"
                      : "bg-surface-2 text-faint"
                }`}
                style={{ height: ROW_HEIGHT }}
              >
                {row.name}
              </div>
            ))}
          </div>

          {/* Note grid */}
          <div
            ref={gridRef}
            data-testid="roll-grid"
            className="relative cursor-crosshair"
            style={{ width: gridWidth, height: gridHeight }}
            onClick={handleGridClick}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
          >
            {/* Row stripes */}
            {rows.map((row, index) => (
              <div
                key={row.midi}
                className={`absolute left-0 right-0 border-b border-line/50 ${
                  row.isRoot ? "bg-red-500/5" : row.inScale ? "" : "bg-black/10"
                }`}
                style={{ top: index * ROW_HEIGHT, height: ROW_HEIGHT }}
              />
            ))}
            {/* Beat lines */}
            {Array.from({ length: totalBeats + 1 }, (_, beat) => (
              <div
                key={beat}
                className={`absolute top-0 bottom-0 ${
                  beat % beatsPerBar === 0 ? "border-l-2 border-line" : "border-l border-line/40"
                }`}
                style={{ left: beat * BEAT_WIDTH }}
              />
            ))}
            {/* Bar numbers */}
            {Array.from({ length: bars }, (_, bar) => (
              <span
                key={bar}
                className="absolute top-0 text-[8px] text-faint font-mono pl-0.5 select-none"
                style={{ left: bar * beatsPerBar * BEAT_WIDTH }}
              >
                {bar + 1}
              </span>
            ))}
            {/* Notes */}
            {notes.map((note) => {
              const rowIndex = rowIndexByMidi.get(note.midi);
              if (rowIndex === undefined) return null;
              const isSelected = selected.has(note.id);
              return (
                <div
                  key={note.id}
                  data-testid={`note-${note.id}`}
                  className={`absolute rounded-sm border ${
                    isSelected
                      ? "bg-accent border-white z-20"
                      : "bg-accent/70 border-accent z-10"
                  }`}
                  style={{
                    left: note.start * BEAT_WIDTH,
                    top: rowIndex * ROW_HEIGHT + 2,
                    width: Math.max(6, note.duration * BEAT_WIDTH - 1),
                    height: ROW_HEIGHT - 4,
                    opacity: 0.4 + (note.velocity / 127) * 0.6,
                  }}
                  onClick={(e) => handleNoteClick(e, note)}
                  onDoubleClick={(e) => handleNoteDoubleClick(e, note)}
                  onPointerDown={(e) => handleNotePointerDown(e, note, "move")}
                >
                  {/* Resize handle */}
                  <div
                    data-testid={`resize-${note.id}`}
                    className="absolute right-0 top-0 bottom-0 w-1.5 cursor-ew-resize"
                    onPointerDown={(e) => handleNotePointerDown(e, note, "resize")}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Velocity lane */}
      <div className="mt-1 border border-line rounded-control bg-surface-2 overflow-x-auto">
        <div className="flex items-end relative" style={{ width: KEY_WIDTH + gridWidth, height: VELOCITY_LANE_HEIGHT }}>
          <div
            className="flex-shrink-0 sticky left-0 z-10 flex items-center justify-end pr-1 text-[9px] text-faint font-mono bg-surface-2 h-full"
            style={{ width: KEY_WIDTH }}
          >
            Vel
          </div>
          <div className="relative h-full" style={{ width: gridWidth }}>
            {notes.map((note) => (
              <input
                key={note.id}
                type="range"
                min={1}
                max={127}
                value={note.velocity}
                aria-label={`Velocity for note ${note.id}`}
                onChange={(e) => handleVelocityChange(note, Number(e.target.value))}
                className="absolute origin-bottom-left -rotate-90 accent-current"
                style={{
                  left: note.start * BEAT_WIDTH + 4,
                  bottom: 0,
                  width: VELOCITY_LANE_HEIGHT - 6,
                  height: 10,
                }}
              />
            ))}
          </div>
        </div>
      </div>

      <p className="mt-1 text-[10px] text-faint">
        Pencil: click to add, drag to move, drag right edge to resize, double-click to erase.
        Shift-click for multi-select. Root notes highlighted like MPC pads.
      </p>
    </div>
  );
}
