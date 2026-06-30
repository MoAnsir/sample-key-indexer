import { useState, useEffect, useCallback } from "react";
import { startScan, fetchScanStatus, reloadIndex, type ScanJob } from "../api/client";
import { suggestLibraryId, isAbsolutePath } from "../lib/folder-picker";
import FolderBrowser from "./FolderBrowser";

interface ScanWizardProps {
  onClose: () => void;
  onComplete: () => void;
}

type Step = "source" | "mode" | "destination" | "options" | "progress" | "done";

export default function ScanWizard({ onClose, onComplete }: ScanWizardProps) {
  const [step, setStep] = useState<Step>("source");
  const [source, setSource] = useState("");
  const [mode, setMode] = useState<"catalog" | "organize">("catalog");
  const [output, setOutput] = useState("");
  const [libraryId, setLibraryId] = useState("");
  const [libraryName, setLibraryName] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [workers, setWorkers] = useState(1);
  const [job, setJob] = useState<ScanJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Auto-suggest library ID from source path
  useEffect(() => {
    if (source && !libraryId) {
      setLibraryId(suggestLibraryId(source));
      setLibraryName(source.split("/").pop() ?? "");
    }
  }, [source, libraryId]);

  const handleStartScan = useCallback(async () => {
    setError(null);
    try {
      const result = await startScan(source, output, mode, {
        library_id: libraryId || undefined,
        library_name: libraryName || undefined,
        dry_run: dryRun || undefined,
        workers,
      });
      setJob(result);
      setStep("progress");
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    }
  }, [source, output, mode, libraryId, libraryName, dryRun]);

  // Poll scan status while running
  useEffect(() => {
    if (step !== "progress") return;
    const interval = setInterval(async () => {
      try {
        const status = await fetchScanStatus();
        setJob(status);
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(interval);
          if (status.status === "completed" && status.index_path) {
            try {
              await reloadIndex(status.index_path);
            } catch {
              // Non-fatal
            }
          }
          setStep("done");
        }
      } catch {
        // ignore poll errors
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [step]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 animate-fade-in">
      <div className="bg-surface rounded-panel shadow-pop w-full max-w-2xl mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <h2 className="text-lg font-display font-bold text-ink">
            {step === "progress" ? "Scanning..." : step === "done" ? "Scan Complete" : "Scan From..."}
          </h2>
          {step !== "progress" && (
            <button onClick={onClose} className="text-faint hover:text-ink text-xl">✕</button>
          )}
        </div>

        <div className="p-6">
          {step === "source" && (
            <StepSource
              source={source}
              setSource={setSource}
              onNext={() => setStep("mode")}
            />
          )}

          {step === "mode" && (
            <StepMode
              mode={mode}
              setMode={setMode}
              onBack={() => setStep("source")}
              onNext={() => setStep("destination")}
            />
          )}

          {step === "destination" && (
            <StepDestination
              mode={mode}
              output={output}
              setOutput={setOutput}
              onBack={() => setStep("mode")}
              onNext={() => setStep("options")}
            />
          )}

          {step === "options" && (
            <StepOptions
              source={source}
              output={output}
              mode={mode}
              libraryId={libraryId}
              setLibraryId={setLibraryId}
              libraryName={libraryName}
              setLibraryName={setLibraryName}
              dryRun={dryRun}
              setDryRun={setDryRun}
              workers={workers}
              setWorkers={setWorkers}
              error={error}
              onBack={() => setStep("destination")}
              onStart={handleStartScan}
            />
          )}

          {step === "progress" && job && (
            <StepProgress job={job} />
          )}

          {step === "done" && job && (
            <StepDone
              job={job}
              onClose={() => { onComplete(); onClose(); }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function StepSource({ source, setSource, onNext }: {
  source: string;
  setSource: (v: string) => void;
  onNext: () => void;
}) {
  const valid = source.trim() && isAbsolutePath(source.trim());
  return (
    <div className="space-y-4">
      <div>
        <label className="chip-label mb-1 block">Source folder</label>
        <p className="text-xs text-muted mb-2">
          The folder containing your audio samples (USB stick, hard drive, or local folder).
        </p>
        <FolderBrowser
          value={source}
          onChange={setSource}
          placeholder="/Volumes/USB_01/Samples"
        />
        {source && !valid && (
          <p className="text-xs text-warn mt-1">Enter a full absolute path</p>
        )}
      </div>
      <div className="flex justify-end">
        <button
          disabled={!valid}
          onClick={onNext}
          className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
        >
          Next →
        </button>
      </div>
    </div>
  );
}

function StepMode({ mode, setMode, onBack, onNext }: {
  mode: "catalog" | "organize";
  setMode: (v: "catalog" | "organize") => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className="chip-label mb-2 block">What do you want to do?</label>
        <div className="space-y-2">
          <button
            onClick={() => setMode("catalog")}
            className={`w-full text-left p-3 rounded-panel border transition-all ${
              mode === "catalog"
                ? "border-accent bg-accent-soft shadow-sm"
                : "border-line bg-surface hover:border-accent"
            }`}
          >
            <p className="text-sm font-semibold text-ink">Scan only (catalog)</p>
            <p className="text-xs text-muted mt-0.5">
              Analyze samples and build a metadata index. No files are copied or moved.
              Use this to catalog USB sticks and external drives.
            </p>
          </button>
          <button
            onClick={() => setMode("organize")}
            className={`w-full text-left p-3 rounded-panel border transition-all ${
              mode === "organize"
                ? "border-accent bg-accent-soft shadow-sm"
                : "border-line bg-surface hover:border-accent"
            }`}
          >
            <p className="text-sm font-semibold text-ink">Scan & organize</p>
            <p className="text-xs text-muted mt-0.5">
              Analyze samples and copy them into folders organized by key and type
              (e.g., Key/A_minor/BassLoops/).
            </p>
          </button>
        </div>
      </div>
      <div className="flex justify-between">
        <button onClick={onBack} className="px-4 py-2 text-sm text-muted hover:text-ink">← Back</button>
        <button
          onClick={onNext}
          className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90 transition-opacity"
        >
          Next →
        </button>
      </div>
    </div>
  );
}

function StepDestination({ mode, output, setOutput, onBack, onNext }: {
  mode: string;
  output: string;
  setOutput: (v: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const valid = output.trim() && isAbsolutePath(output.trim());
  return (
    <div className="space-y-4">
      <div>
        <label className="chip-label mb-1 block">
          {mode === "organize" ? "Destination folder" : "Index storage location"}
        </label>
        <p className="text-xs text-muted mb-2">
          {mode === "organize"
            ? "Where to copy organized samples and store the metadata index."
            : "Where to store the metadata index (no audio files will be copied)."}
        </p>
        <FolderBrowser
          value={output}
          onChange={setOutput}
          placeholder={mode === "organize" ? "~/Desktop/Samples_Organised" : "~/SampleIndexes/my_library"}
        />
        {output && !valid && (
          <p className="text-xs text-warn mt-1">Enter a full absolute path</p>
        )}
      </div>
      <div className="flex justify-between">
        <button onClick={onBack} className="px-4 py-2 text-sm text-muted hover:text-ink">← Back</button>
        <button
          disabled={!valid}
          onClick={onNext}
          className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
        >
          Next →
        </button>
      </div>
    </div>
  );
}

function StepOptions({ source, output, mode, libraryId, setLibraryId, libraryName, setLibraryName, dryRun, setDryRun, workers, setWorkers, error, onBack, onStart }: {
  source: string;
  output: string;
  mode: string;
  libraryId: string;
  setLibraryId: (v: string) => void;
  libraryName: string;
  setLibraryName: (v: string) => void;
  dryRun: boolean;
  setDryRun: (v: boolean) => void;
  workers: number;
  setWorkers: (v: number) => void;
  error: string | null;
  onBack: () => void;
  onStart: () => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className="chip-label mb-2 block">Confirm scan settings</label>
        <div className="space-y-2 text-sm">
          <div className="flex gap-2">
            <span className="text-muted w-20 shrink-0">Source:</span>
            <span className="text-ink font-mono text-xs truncate">{source}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-muted w-20 shrink-0">Output:</span>
            <span className="text-ink font-mono text-xs truncate">{output}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-muted w-20 shrink-0">Mode:</span>
            <span className="text-ink">{mode === "catalog" ? "Scan only" : "Scan & organize"}</span>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <div>
          <label className="chip-label mb-1 block">Library ID</label>
          <input
            type="text"
            className="input-base w-full"
            value={libraryId}
            onChange={(e) => setLibraryId(e.target.value)}
          />
        </div>
        <div>
          <label className="chip-label mb-1 block">Library Name</label>
          <input
            type="text"
            className="input-base w-full"
            value={libraryName}
            onChange={(e) => setLibraryName(e.target.value)}
          />
        </div>
        <div>
          <label className="chip-label mb-1 block">Analysis Workers</label>
          <div className="flex items-center gap-3">
            <select
              className="input-base"
              value={workers}
              onChange={(e) => setWorkers(Number(e.target.value))}
            >
              <option value={1}>1 (safe — skips failures)</option>
              <option value={2}>2</option>
              <option value={4}>4 (faster but crashes affect batch)</option>
              <option value={8}>8</option>
            </select>
            <span className="text-xs text-faint">
              Use 1 worker for reliability, more for speed
            </span>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          Dry run (analyze without copying files)
        </label>
      </div>

      {error && (
        <p className="text-sm text-warn bg-warn/10 rounded-control px-3 py-2">{error}</p>
      )}

      <div className="flex justify-between">
        <button onClick={onBack} className="px-4 py-2 text-sm text-muted hover:text-ink">← Back</button>
        <button
          onClick={onStart}
          className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90 transition-opacity"
        >
          Start Scan
        </button>
      </div>
    </div>
  );
}

function StepProgress({ job }: { job: ScanJob }) {
  const pct = job.total_files > 0
    ? Math.round((job.processed_files / job.total_files) * 100)
    : 0;
  const elapsed = job.started_at ? Math.round(Date.now() / 1000 - job.started_at) : 0;

  const phaseLabels: Record<string, string> = {
    discovering: "Discovering audio files...",
    analyzing: "Analyzing samples...",
    indexing: "Writing index...",
    saving: "Saving metadata...",
  };

  return (
    <div className="space-y-4">
      {/* Phase + file count */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full shrink-0" />
          <span className="text-sm text-ink">
            {phaseLabels[job.phase] ?? "Starting..."}
          </span>
        </div>
        <span className="text-xs text-muted font-mono">
          {elapsed}s elapsed
        </span>
      </div>

      {/* Progress bar */}
      {job.total_files > 0 && (
        <div>
          <div className="flex justify-between text-xs text-muted mb-1">
            <span>{job.processed_files.toLocaleString()} / {job.total_files.toLocaleString()} files</span>
            <span className="font-mono">{pct}%</span>
          </div>
          <div className="w-full h-2 rounded-full bg-surface-2 overflow-hidden">
            <div
              className="h-full rounded-full bg-accent transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      {/* Log output */}
      <details open={job.progress_lines.length < 20}>
        <summary className="text-xs text-muted cursor-pointer mb-1">
          Output ({job.total_lines} lines)
        </summary>
        <div className="bg-surface-2 rounded-control p-3 max-h-48 overflow-y-auto font-mono text-[11px] text-muted space-y-0.5">
          {job.progress_lines.length === 0 ? (
            <p>Waiting for output...</p>
          ) : (
            job.progress_lines.slice(-30).map((line, i) => (
              <p key={i}>{line}</p>
            ))
          )}
        </div>
      </details>

      <p className="text-xs text-faint">Do not close this window while scanning.</p>
    </div>
  );
}

function StepDone({ job, onClose }: { job: ScanJob; onClose: () => void }) {
  const duration = job.started_at && job.finished_at
    ? Math.round(job.finished_at - job.started_at)
    : null;

  return (
    <div className="space-y-4">
      {job.status === "completed" ? (
        <div className="text-center py-4">
          <p className="text-2xl mb-2">✓</p>
          <p className="text-lg font-display font-bold text-good">Scan complete</p>
          {duration && (
            <p className="text-sm text-muted mt-1">Finished in {duration}s</p>
          )}
          <p className="text-xs text-muted mt-2 font-mono">{job.output}</p>
        </div>
      ) : (
        <div className="text-center py-4">
          <p className="text-2xl mb-2">✗</p>
          <p className="text-lg font-display font-bold text-warn">Scan failed</p>
          {job.error && (
            <p className="text-sm text-warn mt-1">{job.error}</p>
          )}
        </div>
      )}

      {job.progress_lines.length > 0 && (
        <details className="text-xs">
          <summary className="text-muted cursor-pointer">Show output ({job.total_lines} lines)</summary>
          <div className="bg-surface-2 rounded-control p-3 max-h-48 overflow-y-auto font-mono text-muted mt-2 space-y-0.5">
            {job.progress_lines.map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </details>
      )}

      <div className="flex justify-end">
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium rounded-control bg-accent text-white hover:opacity-90 transition-opacity"
        >
          Done
        </button>
      </div>
    </div>
  );
}
