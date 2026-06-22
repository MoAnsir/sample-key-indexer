import { useEffect, useRef, useCallback } from "react";
import WaveSurfer from "wavesurfer.js";
import { getAudioUrl } from "../api/client";

interface AudioPlayerProps {
  sampleId: number;
  autoPlay?: boolean;
}

export default function AudioPlayer({ sampleId, autoPlay = false }: AudioPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);

  const destroy = useCallback(() => {
    if (wavesurferRef.current) {
      wavesurferRef.current.destroy();
      wavesurferRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    destroy();

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

    ws.load(getAudioUrl(sampleId));

    if (autoPlay) {
      ws.once("ready", () => ws.play());
    }

    wavesurferRef.current = ws;

    return destroy;
  }, [sampleId, autoPlay, destroy]);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <div ref={containerRef} className="w-full" />
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={() => wavesurferRef.current?.playPause()}
          className="px-3 py-1 text-xs font-medium rounded bg-teal-600 text-white hover:bg-teal-700 transition-colors"
        >
          Play / Pause
        </button>
        <button
          onClick={() => wavesurferRef.current?.stop()}
          className="px-3 py-1 text-xs font-medium rounded bg-gray-200 text-gray-700 hover:bg-gray-300 transition-colors"
        >
          Stop
        </button>
      </div>
    </div>
  );
}
