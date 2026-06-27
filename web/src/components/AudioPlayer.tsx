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

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#99d1c7",
      progressColor: "#0d9488",
      cursorColor: "#0d9488",
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
      console.error("WaveSurfer error:", err);
    });

    ws.load(getAudioUrl(sampleId));
    wavesurferRef.current = ws;

    return destroy;
  }, [sampleId, autoPlay, destroy]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-950/30 dark:border-red-800 p-3 text-sm text-red-700 dark:text-red-400">
        Audio error: {error}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div ref={containerRef} className="w-full" />
      {loading && (
        <p className="text-xs text-faint mt-1">Loading waveform...</p>
      )}
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={() => wavesurferRef.current?.playPause()}
          className="px-3 py-1 text-xs font-medium rounded bg-accent text-white hover:opacity-90 transition-colors"
        >
          Play / Pause
        </button>
        <button
          onClick={() => wavesurferRef.current?.stop()}
          className="px-3 py-1 text-xs font-medium rounded bg-surface-2  text-ink hover:bg-surface-2 dark:hover:bg-gray-600 transition-colors"
        >
          Stop
        </button>
      </div>
    </div>
  );
}
