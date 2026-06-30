import { useState } from "react";
import type { SampleDetail } from "../types/api";

const REASON_EXPLANATIONS: Record<string, { text: string; section?: string }> = {
  engine_key_disagreement: {
    text: "librosa and essentia detected different keys — the analysis engines don't agree on the musical key.",
    section: "section-deep-analysis",
  },
  engine_root_disagreement: {
    text: "librosa and essentia detected different root notes.",
    section: "section-piano",
  },
  filename_key_disagreement: {
    text: "The key detected by analysis doesn't match the key in the filename.",
    section: "section-metadata",
  },
  filename_key_disagreement_weak: {
    text: "Weak key disagreement between filename and analysis (low confidence detection).",
    section: "section-metadata",
  },
  filename_key_disagreement_confident: {
    text: "High-confidence detection that contradicts the key in the filename — one of them is wrong.",
    section: "section-metadata",
  },
  filename_bpm_anchor: {
    text: "BPM in the filename doesn't match the detected BPM.",
    section: "section-musical-record",
  },
  tiny_audio: {
    text: "Sample is very short — not enough audio data for reliable key/pitch detection.",
    section: "section-audio",
  },
  short_signal_fft_adjusted: {
    text: "Signal was too short for standard FFT — analysis used adjusted parameters.",
    section: "section-frequency",
  },
  near_silent: {
    text: "Sample is near-silent — analysis results may be unreliable.",
    section: "section-mfcc",
  },
  low_confidence: {
    text: "Overall confidence in the key detection is low.",
    section: "section-metadata",
  },
};

function scrollToSection(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  const panel = el.closest(".overflow-y-auto");
  if (panel) {
    const panelRect = panel.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    const offset = elRect.top - panelRect.top + panel.scrollTop - 100;
    panel.scrollTo({ top: offset, behavior: "smooth" });
  } else {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  el.classList.add("ring-2", "ring-accent", "ring-offset-2", "rounded-lg");
  setTimeout(() => {
    el.classList.remove("ring-2", "ring-accent", "ring-offset-2", "rounded-lg");
  }, 2000);
}

function extractFilenameKey(filePath: string): string | null {
  const name = filePath.split("/").pop() ?? "";
  const match = name.match(/([A-G][#b]?)[-_\s]?(major|minor|maj|min)/i);
  if (match) {
    const note = match[1];
    const mode = match[2].toLowerCase().startsWith("min") ? "minor" : "major";
    return `${note}_${mode}`;
  }
  return null;
}

interface ReviewDiagnosticProps {
  detail: SampleDetail;
}

export default function ReviewDiagnostic({ detail }: ReviewDiagnosticProps) {
  const reasons = detail.review_reasons ?? [];
  const [collapsed, setCollapsed] = useState(true);

  if (reasons.length === 0) return null;

  const filenameKey = extractFilenameKey(detail.file_path ?? detail.name ?? "");

  const sources: {
    label: string;
    key: string | null;
    root: string | null;
    confidence: number | null;
    bpm: number | null;
    section?: string;
  }[] = [
    {
      label: "Main Analysis (librosa + essentia)",
      key: detail.key,
      root: detail.root_note,
      confidence: detail.confidence,
      bpm: detail.bpm,
      section: "section-metadata",
    },
  ];

  if (detail.deep_key || detail.deep_root) {
    sources.push({
      label: `Deep Analysis (${detail.deep_route_family ?? "unknown route"})`,
      key: detail.deep_key,
      root: detail.deep_root,
      confidence: detail.deep_key_confidence,
      bpm: detail.deep_bpm,
      section: "section-deep-analysis",
    });
  }

  if (detail.musical_record) {
    sources.push({
      label: "Musical Record (combined)",
      key: detail.musical_record.key,
      root: detail.musical_record.tonic,
      confidence: detail.musical_record.confidence,
      bpm: detail.musical_record.bpm,
      section: "section-musical-record",
    });
  }

  if (filenameKey) {
    sources.push({
      label: "Filename",
      key: filenameKey,
      root: filenameKey.split("_")[0],
      confidence: null,
      bpm: null,
    });
  }

  const allKeys = sources.map((s) => s.key).filter(Boolean);
  const uniqueKeys = [...new Set(allKeys)];
  const allAgree = uniqueKeys.length <= 1;

  const libraryId = detail.library_id ?? "LIBRARY_ID";
  const indexPath = `/path/to/metadata_index.sqlite`;

  return (
    <div className="rounded-lg border-2 border-amber-300 dark:border-amber-700 bg-warn/10/50 dark:bg-amber-950/30">
      {/* Header — always visible */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-warn/10 dark:hover:bg-amber-900/50 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-warn">
            Review Diagnostics
          </span>
          <span className="text-xs text-warn">
            {reasons.length} {reasons.length === 1 ? "issue" : "issues"} flagged
          </span>
          {!allAgree && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
              Key disagreement
            </span>
          )}
        </div>
        <span className="text-xs text-amber-500">
          {collapsed ? "▼ Show" : "▲ Hide"}
        </span>
      </button>

      {!collapsed && (
        <div className="px-4 pb-4 space-y-4">
          {/* Reason explanations */}
          <div className="space-y-2">
            {reasons.map((reason) => {
              const info = REASON_EXPLANATIONS[reason];
              return (
                <div
                  key={reason}
                  className="rounded border border-warn/30 bg-surface px-3 py-2"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-mono font-semibold text-warn">
                      {reason}
                    </p>
                    {info?.section && (
                      <button
                        onClick={() => scrollToSection(info.section!)}
                        className="text-[10px] text-accent hover:text-accent underline"
                      >
                        Jump to details ↓
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-warn mt-0.5">
                    {info?.text ?? "Flagged for manual review."}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Engine comparison table */}
          <div className="rounded-lg border border-line bg-surface overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-2 text-left">
                  <th className="px-3 py-2 text-xs font-medium text-muted uppercase">
                    Source
                  </th>
                  <th className="px-3 py-2 text-xs font-medium text-muted uppercase">
                    Key
                  </th>
                  <th className="px-3 py-2 text-xs font-medium text-muted uppercase">
                    Root
                  </th>
                  <th className="px-3 py-2 text-xs font-medium text-muted uppercase">
                    Confidence
                  </th>
                  <th className="px-3 py-2 text-xs font-medium text-muted uppercase">
                    BPM
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {sources.map((s) => {
                  const keyDisagrees =
                    !allAgree && s.key != null && s.key !== uniqueKeys[0];
                  return (
                    <tr key={s.label} className="hover:bg-surface-2 hover:bg-surface-2">
                      <td className="px-3 py-2 text-xs text-muted">
                        {s.section ? (
                          <button
                            onClick={() => scrollToSection(s.section!)}
                            className="text-accent hover:text-accent underline text-left"
                          >
                            {s.label}
                          </button>
                        ) : (
                          s.label
                        )}
                      </td>
                      <td
                        className={`px-3 py-2 text-sm font-medium ${
                          keyDisagrees ? "text-red-600" : "text-ink"
                        }`}
                      >
                        {s.key ?? "—"}
                        {keyDisagrees && " ⚠"}
                      </td>
                      <td className="px-3 py-2 text-sm text-ink">
                        {s.root ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-sm text-ink">
                        {s.confidence != null ? s.confidence.toFixed(3) : "—"}
                      </td>
                      <td className="px-3 py-2 text-sm text-ink">
                        {s.bpm != null ? Math.round(s.bpm) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Assessment */}
          <div className="rounded border border-line bg-surface px-3 py-2">
            <p className="text-xs font-semibold text-ink mb-1">Assessment</p>
            {allAgree ? (
              <p className="text-xs text-green-700">
                All sources agree on <strong>{uniqueKeys[0]}</strong>. The review
                flag is likely due to low confidence or a minor warning. This sample
                is probably correctly classified.
              </p>
            ) : (
              <p className="text-xs text-warn">
                Sources disagree: {uniqueKeys.join(" vs ")}. The highest-confidence
                result is most likely correct. Consider re-running deep analysis or
                manually verifying. See{" "}
                <button
                  onClick={() => scrollToSection("section-deep-analysis")}
                  className="text-accent hover:text-accent underline"
                >
                  Deep Analysis
                </button>{" "}
                and{" "}
                <button
                  onClick={() => scrollToSection("section-musical-record")}
                  className="text-accent hover:text-accent underline"
                >
                  Musical Record
                </button>{" "}
                below for details.
              </p>
            )}
          </div>

          {/* Suggested commands */}
          <div className="rounded border border-line bg-surface px-3 py-2">
            <p className="text-xs font-semibold text-ink mb-1">
              CLI Commands to Investigate
            </p>
            <div className="space-y-1.5">
              <CommandBlock
                label="Re-run deep analysis on review candidates"
                command={`sample-key-indexer-review ${indexPath} --deep-analysis-run --deep-analysis-mode force-all --deep-analysis-scope review --library-root ${libraryId}=/path/to/source`}
              />
              <CommandBlock
                label="Run KeyFinder comparison"
                command={`sample-key-indexer-review ${indexPath} --keyfinder-enrich --keyfinder-scope review --keyfinder-convert-retry`}
              />
              <CommandBlock
                label="Audit classification"
                command={`sample-key-indexer-review ${indexPath} --classification-audit --examples 50`}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CommandBlock({
  label,
  command,
}: {
  label: string;
  command: string;
}) {
  return (
    <div>
      <p className="text-[10px] text-muted">{label}</p>
      <pre className="text-[11px] text-ink bg-surface-2 rounded px-2 py-1 mt-0.5 overflow-x-auto whitespace-pre-wrap break-all">
        {command}
      </pre>
    </div>
  );
}
