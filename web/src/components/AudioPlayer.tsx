import { useEffect, useRef, useCallback, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { getAudioUrl } from "../api/client";

interface AudioPlayerProps {
  sampleId: number;
  autoPlay?: boolean;
}

export default function AudioPlayer({ sampleId, autoPlay = false }: AudioPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const destroy = useCallback(() => {
    if (wavesurferRef.current) {
      wavesurferRef.current.destroy();
      wavesurferRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    destroy();
    setError(null);
    setLoading(true);

    const style = getComputedStyle(document.documentElement);
    const accent = style.getPropertyValue("--accent").trim() || "#0e9384";
    const accentSoft = style.getPropertyValue("--accent-soft").trim() || "#0e93841f";

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: accentSoft,
      progressColor: accent,
      cursorColor: accent,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 64,
      normalize: true,
    });

    ws.on("ready", () => {
      setLoading(false);
      if (autoPlay) ws.play();
    });

    ws.on("error", (err) => {
      setLoading(false);
      setError(typeof err === "string" ? err : "Failed to load audio");
    });

    ws.load(getAudioUrl(sampleId));
    wavesurferRef.current = ws;

    return destroy;
  }, [sampleId, autoPlay, destroy]);

  if (error) {
    return (
      <div className="card border-warn/30 bg-warn/10 text-sm text-warn">
        Audio error: {error}
      </div>
    );
  }

  return (
    <div className="card">
      <div ref={containerRef} className="w-full" />
      {loading && (
        <p className="text-xs text-faint mt-1 font-sans">Loading waveform...</p>
      )}
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={() => wavesurferRef.current?.playPause()}
          className="px-3 py-1 text-xs font-sans font-medium rounded-control bg-accent text-accent-ink hover:opacity-90 transition-opacity"
        >
          ▶ Play / Pause
        </button>
        <button
          onClick={() => wavesurferRef.current?.stop()}
          className="px-3 py-1 text-xs font-sans font-medium rounded-control bg-surface-2 text-muted border border-line hover:text-ink transition-colors"
        >
          ■ Stop
        </button>
      </div>
    </div>
  );
}
