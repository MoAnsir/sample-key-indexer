import { useCallback, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NoteEvent {
  note: string | number;
  midi?: number;
  start: number;
  duration: number;
  velocity?: number;
}

interface SketchSynthProps {
  noteEvents: NoteEvent[];
  bpm: number;
  bars: number;
  beatsPerBar: number;
}

interface SynthParams {
  waveform: OscillatorType;
  cutoff: number;
  resonance: number;
  attack: number;
  decay: number;
  sustain: number;
  release: number;
  volume: number;
}

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

function logMap(t: number, lo: number, hi: number): number {
  return lo * Math.pow(hi / lo, t);
}

function linMap(t: number, lo: number, hi: number): number {
  return lo + t * (hi - lo);
}

function midiToHz(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function eventToMidi(ev: { note: string | number; midi?: number }): number {
  if (typeof ev.midi === "number") return ev.midi;
  if (typeof ev.note === "number") return ev.note;
  const NOTE_ORDER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const FLAT_TO_SHARP: Record<string, string> = {
    Db: "C#", Eb: "D#", Fb: "E", Gb: "F#", Ab: "G#", Bb: "A#", Cb: "B",
  };
  const m = /^([A-Ga-g][#b]?)(-?\d+)?$/.exec(String(ev.note).trim());
  if (!m) return 60;
  let name = m[1][0].toUpperCase() + m[1].slice(1);
  name = FLAT_TO_SHARP[name] ?? name;
  const pc = NOTE_ORDER.indexOf(name);
  if (pc < 0) return 60;
  const oct = m[2] !== undefined ? parseInt(m[2]) : 4;
  return (oct + 1) * 12 + pc;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULTS: SynthParams = {
  waveform: "square",
  cutoff: 0.42,
  resonance: 0.12,
  attack: 0.01,
  decay: 0.18,
  sustain: 0.60,
  release: 0.22,
  volume: 0.65,
};

// ---------------------------------------------------------------------------
// SynthKnob sub-component
// ---------------------------------------------------------------------------

function SynthKnob({
  label,
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.01,
  display,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  display: string;
}) {
  return (
    <div className="min-w-[80px]">
      <div className="flex justify-between text-[10px] text-muted mb-0.5">
        <span className="uppercase tracking-wide">{label}</span>
        <span className="font-mono text-ink">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 accent-[var(--color-accent)] cursor-pointer"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function SketchSynth({ noteEvents, bpm, bars, beatsPerBar }: SketchSynthProps) {
  const [params, setParams] = useState<SynthParams>(DEFAULTS);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);

  const ctxRef = useRef<AudioContext | null>(null);
  const loopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loopEnabledRef = useRef(loop);
  loopEnabledRef.current = loop;

  const set = <K extends keyof SynthParams>(key: K, value: SynthParams[K]) =>
    setParams((p) => ({ ...p, [key]: value }));

  const stop = useCallback(() => {
    if (loopTimerRef.current !== null) {
      clearTimeout(loopTimerRef.current);
      loopTimerRef.current = null;
    }
    if (ctxRef.current) {
      ctxRef.current.close().catch(() => {});
      ctxRef.current = null;
    }
    setPlaying(false);
  }, []);

  const play = useCallback(() => {
    stop();

    const ctx = new AudioContext();
    ctxRef.current = ctx;

    const { waveform, cutoff, resonance, attack, decay, sustain, release, volume } = params;

    const filterNode = ctx.createBiquadFilter();
    filterNode.type = "lowpass";
    filterNode.frequency.value = logMap(cutoff, 80, 18000);
    filterNode.Q.value = linMap(resonance, 0.1, 18);

    const masterGain = ctx.createGain();
    masterGain.gain.value = volume;

    filterNode.connect(masterGain);
    masterGain.connect(ctx.destination);

    const secondsPerBeat = 60 / bpm;

    for (const ev of noteEvents) {
      const tStart = ctx.currentTime + 0.05 + ev.start * secondsPerBeat;
      const tRelease = tStart + ev.duration * secondsPerBeat;
      const tEnd = tRelease + linMap(release, 0.001, 4);
      const peak = (ev.velocity ?? 100) / 127;

      const osc = ctx.createOscillator();
      osc.type = waveform;
      osc.frequency.value = midiToHz(eventToMidi(ev));

      const env = ctx.createGain();
      env.gain.setValueAtTime(0, tStart);
      env.gain.linearRampToValueAtTime(peak, tStart + linMap(attack, 0.001, 2));
      env.gain.linearRampToValueAtTime(
        sustain * peak,
        tStart + linMap(attack, 0.001, 2) + linMap(decay, 0.001, 2),
      );
      env.gain.setValueAtTime(sustain * peak, tRelease);
      env.gain.linearRampToValueAtTime(0, tEnd);

      osc.connect(env);
      env.connect(filterNode);

      osc.start(tStart);
      osc.stop(tEnd);
    }

    const totalDuration = bars * beatsPerBar * secondsPerBeat;
    const loopDelay = (totalDuration + linMap(release, 0.001, 4) + 0.2) * 1000;

    setPlaying(true);

    loopTimerRef.current = setTimeout(() => {
      if (loopEnabledRef.current) {
        play();
      } else {
        stop();
      }
    }, loopDelay);
  }, [params, noteEvents, bpm, bars, beatsPerBar, stop]);

  // Display helpers
  const cutoffHz = logMap(params.cutoff, 80, 18000);
  const cutoffDisplay =
    cutoffHz >= 1000 ? `${(cutoffHz / 1000).toFixed(1)}k` : `${Math.round(cutoffHz)} Hz`;
  const resDisplay = linMap(params.resonance, 0.1, 18).toFixed(1);
  const attackDisplay = `${linMap(params.attack, 0.001, 2).toFixed(2)}s`;
  const decayDisplay = `${linMap(params.decay, 0.001, 2).toFixed(2)}s`;
  const sustainDisplay = `${Math.round(params.sustain * 100)}%`;
  const releaseDisplay = `${linMap(params.release, 0.001, 4).toFixed(2)}s`;
  const volumeDisplay = `${Math.round(params.volume * 100)}%`;

  const waveforms: OscillatorType[] = ["sine", "triangle", "sawtooth", "square"];
  const waveLabels: Record<OscillatorType, string> = {
    sine: "SINE",
    triangle: "TRI",
    sawtooth: "SAW",
    square: "SQR",
    custom: "CUSTOM",
  };

  return (
    <div className="rounded-control border border-line bg-surface-2 p-4 space-y-3">
      {/* Transport row */}
      <div className="flex items-center gap-2">
        <button
          onClick={playing ? undefined : play}
          disabled={playing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-control bg-accent text-white disabled:opacity-70"
        >
          {playing && (
            <span className="animate-pulse inline-block w-2 h-2 rounded-full bg-good" />
          )}
          ▶ Play
        </button>
        <button
          onClick={stop}
          className="px-3 py-1.5 text-xs font-medium rounded-control border border-line text-muted hover:text-ink"
        >
          ■ Stop
        </button>
        <button
          onClick={() => setLoop((l) => !l)}
          className={`px-3 py-1.5 text-xs font-medium rounded-control border ${
            loop
              ? "bg-accent text-white border-accent"
              : "bg-surface border-line text-muted hover:text-ink"
          }`}
        >
          ↺ Loop
        </button>
      </div>

      {/* Sections row */}
      <div className="flex flex-wrap gap-6">
        {/* OSC */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted mb-1">OSC</p>
          <div className="flex gap-1">
            {waveforms.map((w) => (
              <button
                key={w}
                onClick={() => set("waveform", w)}
                className={`px-2 py-0.5 text-[10px] font-medium rounded-full border ${
                  params.waveform === w
                    ? "bg-accent text-white border-accent"
                    : "bg-surface border-line text-muted hover:text-ink"
                }`}
              >
                {waveLabels[w]}
              </button>
            ))}
          </div>
        </div>

        {/* FILTER */}
        <div className="min-w-[120px] space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted mb-1">FILTER</p>
          <SynthKnob
            label="Cutoff"
            value={params.cutoff}
            onChange={(v) => set("cutoff", v)}
            display={cutoffDisplay}
          />
          <SynthKnob
            label="Res"
            value={params.resonance}
            onChange={(v) => set("resonance", v)}
            display={resDisplay}
          />
        </div>

        {/* ENV (ADSR) */}
        <div className="min-w-[160px] space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted mb-1">ENV (ADSR)</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <SynthKnob
              label="A"
              value={params.attack}
              onChange={(v) => set("attack", v)}
              display={attackDisplay}
            />
            <SynthKnob
              label="D"
              value={params.decay}
              onChange={(v) => set("decay", v)}
              display={decayDisplay}
            />
            <SynthKnob
              label="S"
              value={params.sustain}
              onChange={(v) => set("sustain", v)}
              display={sustainDisplay}
            />
            <SynthKnob
              label="R"
              value={params.release}
              onChange={(v) => set("release", v)}
              display={releaseDisplay}
            />
          </div>
        </div>

        {/* AMP */}
        <div className="min-w-[80px] space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted mb-1">AMP</p>
          <SynthKnob
            label="Vol"
            value={params.volume}
            onChange={(v) => set("volume", v)}
            display={volumeDisplay}
          />
        </div>
      </div>
    </div>
  );
}
