import { useCallback, useEffect, useRef, useState } from "react";
import {
  analyzeSketch,
  downloadSketchMidi,
  fetchSketch,
  importMidi,
  saveSketch,
  type SketchAnalysis,
  type SketchPayload,
} from "../api/client";
import PianoRoll from "./PianoRoll";
import SketchResults from "./SketchResults";
import { fromNoteEvents, toNoteEvents, type RollNote } from "../lib/piano-roll";

interface SketchWizardProps {
  onClose: () => void;
  onSaved: () => void;
  /** When set, the wizard loads the existing sketch and opens on the notes step. */
  initialSketchId?: string;
}

type Step = "details" | "notes" | "results";

// Display flats alongside sharps — MPC users think in "Eb minor".
export const TONIC_OPTIONS = [
  { value: "C", label: "C" },
  { value: "C#", label: "C# / Db" },
  { value: "D", label: "D" },
  { value: "D#", label: "D# / Eb" },
  { value: "E", label: "E" },
  { value: "F", label: "F" },
  { value: "F#", label: "F# / Gb" },
  { value: "G", label: "G" },
  { value: "G#", label: "G# / Ab" },
  { value: "A", label: "A" },
  { value: "A#", label: "A# / Bb" },
  { value: "B", label: "B" },
];

export const SKETCH_TYPE_OPTIONS = [
  "Bass",
  "Chords",
  "Drums",
  "FX",
  "Kick",
  "Snare",
  "Hat",
  "Perc",
  "Leads",
  "Pads",
  "Plucks",
  "Vocals",
  "BassLoops",
  "DrumLoops",
  "FXLoops",
  "MelodyLoops",
  "VocalLoops",
];

export const FREQUENCY_REGISTER_OPTIONS = [
  { value: "", label: "Not set" },
  { value: "sub", label: "Sub (20–60 Hz)" },
  { value: "low", label: "Low (60–250 Hz)" },
  { value: "mid", label: "Mid (250 Hz–4 kHz)" },
  { value: "high", label: "High (4 kHz+)" },
];

export default function SketchWizard({ onClose, onSaved, initialSketchId }: SketchWizardProps) {
  const [step, setStep] = useState<Step>(initialSketchId ? "notes" : "details");
  const [sketchId, setSketchId] = useState<string | undefined>(initialSketchId);
  const [name, setName] = useState("");
  const [tonic, setTonic] = useState("C");
  const [mode, setMode] = useState<"major" | "minor">("minor");
  const [bpm, setBpm] = useState("120");
  const [bars, setBars] = useState("8");
  const [beatsPerBar, setBeatsPerBar] = useState("4");
  const [type, setType] = useState("Bass");
  const [frequencyRegister, setFrequencyRegister] = useState("");
  const [analysis, setAnalysis] = useState<SketchAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [rollNotes, setRollNotes] = useState<RollNote[]>([]);
  const [midiImportBusy, setMidiImportBusy] = useState(false);
  const [midiImportError, setMidiImportError] = useState<string | null>(null);
  const midiFileInputRef = useRef<HTMLInputElement>(null);

  // Load existing sketch when editing
  useEffect(() => {
    if (!initialSketchId) return;
    setBusy(true);
    fetchSketch(initialSketchId)
      .then((record) => {
        setName(String(record.name ?? ""));
        // key is stored as "Tonic_mode" e.g. "C#_minor"
        const key = String(record.key ?? "");
        const sep = key.lastIndexOf("_");
        if (sep > 0) {
          setTonic(key.slice(0, sep));
          const m = key.slice(sep + 1);
          if (m === "major" || m === "minor") setMode(m);
        }
        if (record.bpm) setBpm(String(Math.round(record.bpm as number)));
        if (record.bars) setBars(String(record.bars));
        if ((record as Record<string, unknown>).beats_per_bar) setBeatsPerBar(String((record as Record<string, unknown>).beats_per_bar));
        if (record.type) setType(String(record.type));
        const fr = (record as Record<string, unknown>).frequency_register;
        setFrequencyRegister(fr ? String(fr) : "");
        const events = (record as Record<string, unknown>).note_events;
        if (Array.isArray(events) && events.length > 0) {
          setRollNotes(fromNoteEvents(events as Parameters<typeof fromNoteEvents>[0]));
        }
      })
      .catch((err) => setError(String(err instanceof Error ? err.message : err)))
      .finally(() => setBusy(false));
  }, [initialSketchId]);

  const handleMidiImport = useCallback(async (file: File) => {
    setMidiImportError(null);
    setMidiImportBusy(true);
    try {
      const result = await importMidi(file);
      if (!result.ok || !result.sketch) {
        setMidiImportError((result.errors ?? ["Import failed"]).join("; "));
        return;
      }
      const { bpm: importedBpm, bars: importedBars, beats_per_bar, note_events } = result.sketch;
      setBpm(String(Math.round(importedBpm)));
      setBars(String(importedBars));
      setBeatsPerBar(String(beats_per_bar));
      setRollNotes(fromNoteEvents(note_events));
    } catch (err) {
      setMidiImportError(String(err instanceof Error ? err.message : err));
    } finally {
      setMidiImportBusy(false);
    }
  }, []);

  const buildPayload = useCallback((): SketchPayload => {
    return {
      name: name.trim() || "Untitled Sketch",
      tonic,
      mode,
      bpm: Number(bpm),
      bars: Number(bars),
      beats_per_bar: Number(beatsPerBar),
      type,
      frequency_register: frequencyRegister || null,
      ...(rollNotes.length > 0 ? { note_events: toNoteEvents(rollNotes) } : {}),
      ...(sketchId ? { sketch_id: sketchId } : {}),
    };
  }, [name, tonic, mode, bpm, bars, beatsPerBar, type, frequencyRegister, rollNotes, sketchId]);

  const bpmValid = Number(bpm) >= 20 && Number(bpm) <= 400;
  const barsValid = Number(bars) >= 1 && Number(bars) <= 128;
  const formValid = bpmValid && barsValid;

  const handleAnalyze = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      const result = await analyzeSketch(buildPayload());
      setAnalysis(result);
      setStep("results");
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  }, [buildPayload]);

  const handleSave = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      const record = await saveSketch(buildPayload());
      setSketchId(record.sketch_id);
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  }, [buildPayload, onSaved]);

  const [midiBusy, setMidiBusy] = useState(false);

  const handleDownloadMidi = useCallback(async () => {
    setError(null);
    setMidiBusy(true);
    try {
      const payload = buildPayload();
      const blob = await downloadSketchMidi(payload);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${(payload.name || "sketch").replace(/[^A-Za-z0-9_-]+/g, "_")}.mid`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setMidiBusy(false);
    }
  }, [buildPayload]);

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-canvas animate-fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-line bg-surface flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="px-2.5 py-1.5 text-xs rounded-control border border-line text-muted hover:text-ink"
            aria-label="Back to library"
          >
            ← Library
          </button>
          <h2 className="text-lg font-display font-bold text-ink">
            {step === "results"
              ? "Sketch Analysis"
              : step === "notes"
                ? initialSketchId ? "Edit Notes" : "Enter Notes"
                : initialSketchId ? "Edit Sketch" : "New Sketch"}
          </h2>
        </div>
        <StepIndicator step={step} />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className={step === "notes" ? "p-6" : "p-6 max-w-3xl mx-auto"}>
          {error && (
            <div className="mb-4 rounded border border-red-300 bg-red-50 dark:bg-red-950/30 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {step === "details" && (
            <div className="space-y-4">
              <Field label="Name">
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. MPC bass idea"
                  className="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-sm text-ink"
                />
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Key">
                  <select
                    value={tonic}
                    onChange={(e) => setTonic(e.target.value)}
                    className="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-sm text-ink"
                  >
                    {TONIC_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Scale">
                  <div className="flex gap-1 bg-surface-2 border border-line rounded-control p-0.5">
                    {(["minor", "major"] as const).map((m) => (
                      <button
                        key={m}
                        onClick={() => setMode(m)}
                        className={`flex-1 px-3 py-1.5 text-sm font-medium rounded-chip transition-colors ${
                          mode === m ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"
                        }`}
                      >
                        {m === "minor" ? "Minor" : "Major"}
                      </button>
                    ))}
                  </div>
                </Field>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <Field label="BPM">
                  <input
                    type="number"
                    min={20}
                    max={400}
                    value={bpm}
                    onChange={(e) => setBpm(e.target.value)}
                    className={`w-full rounded-control border px-3 py-2 text-sm text-ink bg-surface-2 ${
                      bpmValid ? "border-line" : "border-red-400"
                    }`}
                  />
                </Field>
                <Field label="Bars">
                  <input
                    type="number"
                    min={1}
                    max={128}
                    value={bars}
                    onChange={(e) => setBars(e.target.value)}
                    className={`w-full rounded-control border px-3 py-2 text-sm text-ink bg-surface-2 ${
                      barsValid ? "border-line" : "border-red-400"
                    }`}
                  />
                </Field>
                <Field label="Beats / Bar">
                  <select
                    value={beatsPerBar}
                    onChange={(e) => setBeatsPerBar(e.target.value)}
                    className="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-sm text-ink"
                  >
                    {["3", "4", "6", "7"].map((v) => (
                      <option key={v} value={v}>
                        {v}/4
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Type">
                  <select
                    value={type}
                    onChange={(e) => setType(e.target.value)}
                    className="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-sm text-ink"
                  >
                    {SKETCH_TYPE_OPTIONS.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Frequency Register">
                  <select
                    value={frequencyRegister}
                    onChange={(e) => setFrequencyRegister(e.target.value)}
                    className="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-sm text-ink"
                  >
                    {FREQUENCY_REGISTER_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm rounded-control border border-line text-muted hover:text-ink"
                >
                  Cancel
                </button>
                <button
                  onClick={() => setStep("notes")}
                  disabled={!formValid}
                  className="px-4 py-2 text-sm rounded-control border border-accent text-accent hover:bg-accent-soft disabled:opacity-50"
                >
                  Next: Notes
                </button>
                <button
                  onClick={handleAnalyze}
                  disabled={!formValid || busy}
                  className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90 disabled:opacity-50"
                >
                  {busy ? "Analyzing..." : "Analyze"}
                </button>
              </div>
            </div>
          )}

          {step === "notes" && (
            <div className="space-y-3">
              {/* MIDI import zone */}
              <div
                className="flex items-center gap-3 rounded-lg border border-dashed border-line bg-surface-2 px-4 py-3 text-xs text-muted"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const file = e.dataTransfer.files[0];
                  if (file) handleMidiImport(file);
                }}
              >
                <input
                  ref={midiFileInputRef}
                  type="file"
                  accept=".mid,.midi"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleMidiImport(file);
                    e.target.value = "";
                  }}
                />
                <span className="text-base">🎹</span>
                <span className="flex-1">
                  {midiImportBusy
                    ? "Importing…"
                    : "Drop an MPC MIDI export here, or"}
                </span>
                <button
                  onClick={() => midiFileInputRef.current?.click()}
                  disabled={midiImportBusy}
                  className="px-2.5 py-1 rounded-control border border-line text-muted hover:text-ink disabled:opacity-50 text-xs"
                >
                  Browse…
                </button>
              </div>
              {midiImportError && (
                <p className="text-xs text-warn">{midiImportError}</p>
              )}

              <p className="text-xs text-muted">
                Grid view for <span className="text-ink font-medium">{tonic} {mode}</span> at{" "}
                <span className="text-ink font-medium">{bpm} BPM</span>, {bars} bars of {beatsPerBar}/4.
                Rows are filtered to the scale — toggle Chromatic to see all notes.
              </p>
              <PianoRoll
                tonic={tonic}
                mode={mode}
                bars={Number(bars)}
                beatsPerBar={Number(beatsPerBar)}
                notes={rollNotes}
                onChange={setRollNotes}
                gridMaxHeight="calc(100vh - 330px)"
              />
              <div className="flex justify-between items-center pt-2">
                <p className="text-xs text-muted">
                  {rollNotes.length === 0
                    ? "No notes yet — you can also analyze without notes."
                    : `${rollNotes.length} note${rollNotes.length === 1 ? "" : "s"} entered.`}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setStep("details")}
                    className="px-4 py-2 text-sm rounded-control border border-line text-muted hover:text-ink"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleAnalyze}
                    disabled={busy}
                    className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90 disabled:opacity-50"
                  >
                    {busy ? "Analyzing..." : "Analyze"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {step === "results" && analysis && (
            <div className="space-y-4">
              <SketchResults
                analysis={analysis}
                hasNotes={rollNotes.length > 0}
                onDownloadMidi={handleDownloadMidi}
                midiBusy={midiBusy}
                sketchId={sketchId}
                payload={buildPayload()}
                sketchName={name}
              />

              {saved ? (
                <div className="rounded border border-green-300 bg-green-50 dark:bg-green-950/30 px-3 py-2 text-sm text-green-700">
                  Sketch saved — it now appears in your Sketches library.
                </div>
              ) : null}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setStep(rollNotes.length > 0 ? "notes" : "details")}
                  className="px-4 py-2 text-sm rounded-control border border-line text-muted hover:text-ink"
                >
                  Back
                </button>
                {saved ? (
                  <button
                    onClick={onClose}
                    className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90"
                  >
                    Done
                  </button>
                ) : (
                  <button
                    onClick={handleSave}
                    disabled={busy}
                    className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90 disabled:opacity-50"
                  >
                    {busy ? "Saving..." : sketchId ? "Update Sketch" : "Save Sketch"}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StepIndicator({ step }: { step: Step }) {
  const steps: { id: Step; label: string }[] = [
    { id: "details", label: "1 · Details" },
    { id: "notes", label: "2 · Notes" },
    { id: "results", label: "3 · Analysis" },
  ];
  return (
    <div className="flex gap-1 text-xs">
      {steps.map((s) => (
        <span
          key={s.id}
          className={`px-2 py-1 rounded-chip ${
            s.id === step ? "bg-accent-soft text-accent font-medium" : "text-faint"
          }`}
        >
          {s.label}
        </span>
      ))}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-semibold uppercase tracking-wide text-muted mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

