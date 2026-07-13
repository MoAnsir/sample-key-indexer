import { useCallback, useState } from "react";
import {
  analyzeSketch,
  saveSketch,
  type SketchAnalysis,
  type SketchPayload,
} from "../api/client";

interface SketchWizardProps {
  onClose: () => void;
  onSaved: () => void;
}

type Step = "details" | "results";

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

export default function SketchWizard({ onClose, onSaved }: SketchWizardProps) {
  const [step, setStep] = useState<Step>("details");
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
    };
  }, [name, tonic, mode, bpm, bars, beatsPerBar, type, frequencyRegister]);

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
      await saveSketch(buildPayload());
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  }, [buildPayload, onSaved]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 animate-fade-in">
      <div className="bg-surface rounded-panel shadow-pop w-full max-w-2xl mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <h2 className="text-lg font-display font-bold text-ink">
            {step === "results" ? "Sketch Analysis" : "New Sketch"}
          </h2>
          <button onClick={onClose} className="text-faint hover:text-ink text-xl" aria-label="Close">
            ✕
          </button>
        </div>

        <div className="p-6 max-h-[70vh] overflow-y-auto">
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
                  onClick={handleAnalyze}
                  disabled={!formValid || busy}
                  className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90 disabled:opacity-50"
                >
                  {busy ? "Analyzing..." : "Analyze"}
                </button>
              </div>
            </div>
          )}

          {step === "results" && analysis && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <SummaryChip label="Key" value={analysis.context.musical_record.key ?? "—"} />
                <SummaryChip label="Mood" value={analysis.context.mood_profile.primary} />
                <SummaryChip
                  label="BPM"
                  value={String(analysis.context.musical_record.bpm ?? "—")}
                />
                <SummaryChip
                  label="Scale notes"
                  value={analysis.context.musical_record.notes.join(" ")}
                />
              </div>

              {analysis.out_of_scale_notes.length > 0 && (
                <div className="rounded border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn">
                  Out-of-scale notes: {analysis.out_of_scale_notes.join(", ")}
                </div>
              )}

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted mb-1">
                  Compatible keys
                </p>
                <ul className="text-sm text-ink space-y-0.5">
                  {analysis.context.compatibility.keys.map((k) => (
                    <li key={k.label}>
                      <span className="text-muted">{k.label}:</span> {k.scale}
                    </li>
                  ))}
                </ul>
              </div>

              {saved ? (
                <div className="rounded border border-green-300 bg-green-50 dark:bg-green-950/30 px-3 py-2 text-sm text-green-700">
                  Sketch saved — it now appears in your Sketches library.
                </div>
              ) : null}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setStep("details")}
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
                    {busy ? "Saving..." : "Save Sketch"}
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

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-control border border-line bg-surface-2 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="text-sm font-medium text-ink">{value}</p>
    </div>
  );
}
