import type { CatalogResponse, Sample, SampleDetail } from "../types/api";

const BASE = "";

export async function fetchCatalog(): Promise<CatalogResponse> {
  const res = await fetch(`${BASE}/api/catalog`);
  if (!res.ok) throw new Error(`catalog: ${res.status}`);
  return res.json();
}

export interface SamplesResponse {
  total: number;
  offset: number;
  limit: number;
  returned: number;
  samples: Sample[];
}

export async function fetchSamples(
  libraryId: string,
  offset: number = 0,
  limit: number = 15000,
): Promise<SamplesResponse> {
  const params = new URLSearchParams({
    library_id: libraryId,
    offset: String(offset),
    limit: String(limit),
  });
  const res = await fetch(`${BASE}/api/samples?${params}`);
  if (!res.ok) throw new Error(`samples: ${res.status}`);
  return res.json();
}

export async function fetchSampleDetail(id: number): Promise<SampleDetail> {
  const res = await fetch(`${BASE}/api/sample?id=${id}`);
  if (!res.ok) throw new Error(`sample detail: ${res.status}`);
  const data = await res.json();
  return (data.sample ?? data) as SampleDetail;
}

export function getAudioUrl(id: number): string {
  return `${BASE}/api/audio?id=${id}`;
}

export function getMidiUrl(id: number, progressionIndex: number): string {
  return `${BASE}/api/sample-midi?id=${id}&progression=${progressionIndex}`;
}

export async function postReview(
  id: number,
  reviewed: boolean,
): Promise<void> {
  const res = await fetch(`${BASE}/api/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, reviewed }),
  });
  if (!res.ok) throw new Error(`review: ${res.status}`);
}

// Folder browser

export interface FolderEntry {
  name: string;
  path: string;
}

export interface BrowseFoldersResponse {
  path: string;
  folders: FolderEntry[];
  parent: string | null;
  error?: string;
}

export async function browseFolders(path?: string): Promise<BrowseFoldersResponse> {
  const params = path ? `?path=${encodeURIComponent(path)}` : "";
  const res = await fetch(`${BASE}/api/browse-folders${params}`);
  return res.json();
}

// Scan API

export interface ScanJob {
  job_id: string;
  source: string;
  output: string;
  mode: string;
  status: "pending" | "running" | "completed" | "failed" | "idle";
  progress_lines: string[];
  error: string | null;
  started_at: number | null;
  finished_at: number | null;
  total_lines: number;
  total_files: number;
  processed_files: number;
  current_file: string;
  phase: string;
  index_path: string | null;
}

export interface ScanHistoryEntry {
  source: string;
  output: string;
  mode: string;
  scanned_at: number;
  index_path: string | null;
}

export async function startScan(
  source: string,
  output: string,
  mode: "catalog" | "organize",
  options?: Record<string, unknown>,
): Promise<ScanJob> {
  const res = await fetch(`${BASE}/api/scan/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, output, mode, options }),
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data.job;
}

export async function fetchScanStatus(): Promise<ScanJob> {
  const res = await fetch(`${BASE}/api/scan/status`);
  return res.json();
}

export async function fetchScanHistory(): Promise<ScanHistoryEntry[]> {
  const res = await fetch(`${BASE}/api/scan/history`);
  const data = await res.json();
  return data.history ?? [];
}

export async function addIndexToHistory(indexPath: string, source?: string, output?: string): Promise<void> {
  await fetch(`${BASE}/api/scan/add-index`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index_path: indexPath, source: source ?? "", output: output ?? "" }),
  });
}

export async function reloadIndex(indexPath?: string): Promise<void> {
  await fetch(`${BASE}/api/reload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index_path: indexPath ?? "" }),
  });
}

export async function deleteScanData(output: string): Promise<{ deleted: string[]; errors: string[] }> {
  const res = await fetch(`${BASE}/api/scan/delete-data`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ output }),
  });
  return res.json();
}

export async function removeIndexFromHistory(indexPath: string): Promise<void> {
  await fetch(`${BASE}/api/scan/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index_path: indexPath }),
  });
}

// Sketches

export interface SketchNoteEvent {
  note: string | number;
  start: number;
  duration: number;
  velocity?: number;
}

export interface SketchPayload {
  name: string;
  tonic: string;
  mode: "major" | "minor";
  bpm: number;
  bars: number;
  beats_per_bar?: number;
  type: string;
  frequency_register?: string | null;
  notes?: string[];
  note_events?: SketchNoteEvent[];
  sketch_id?: string;
}

export interface SketchCompatKey {
  label: string;
  key: string;
  scale: string;
  notes: string[];
  chords: string[];
}

export interface SketchProgression {
  name: string;
  mood: string;
  progression: string[];
  roman: string[];
  notes_to_play: string[];
}

export interface SketchMusicalContext {
  musical_record: {
    tonic: string | null;
    mode: string | null;
    key: string | null;
    scale: string | null;
    notes: string[];
    chords: string[];
    bpm: number | null;
    confidence: number | null;
  };
  compatibility: {
    keys: SketchCompatKey[];
    progressions: SketchProgression[];
  };
  mood_profile: {
    primary: string;
    supporting: string[];
    transitions: string[];
    reasons: string[];
  };
  transition_suggestions: { label: string; why: string }[];
}

export interface SketchAnalysis {
  ok: boolean;
  sketch: Record<string, unknown>;
  sample: Record<string, unknown>;
  context: SketchMusicalContext;
  out_of_scale_notes: string[];
  errors?: string[];
}

export interface SketchRecord extends Record<string, unknown> {
  sketch_id: string;
  name: string;
  key: string;
  bpm: number;
  type: string;
  created_at: string;
}

export interface MidiImportResult {
  ok: boolean;
  sketch?: {
    bpm: number;
    bars: number;
    beats_per_bar: number;
    note_events: SketchNoteEvent[];
    tonic: null;
    mode: null;
    type: null;
    name: null;
    frequency_register: null;
  };
  errors?: string[];
}

export async function importMidi(file: File): Promise<MidiImportResult> {
  const res = await fetch(`${BASE}/api/sketch/import-midi`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });
  const data = await res.json();
  return data as MidiImportResult;
}

export async function fetchSketch(sketchId: string): Promise<SketchRecord> {
  const res = await fetch(`${BASE}/api/sketch?sketch_id=${encodeURIComponent(sketchId)}`);
  if (!res.ok) throw new Error(`sketch: ${res.status}`);
  const data = await res.json();
  return data.sketch as SketchRecord;
}

async function postSketch(path: string, payload: SketchPayload | { sketch_id: string }): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function analyzeSketch(payload: SketchPayload): Promise<SketchAnalysis> {
  const res = await postSketch("/api/sketch/analyze", payload);
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error((data.errors ?? [`analyze: ${res.status}`]).join("; "));
  }
  return data;
}

export async function saveSketch(payload: SketchPayload): Promise<SketchRecord> {
  const res = await postSketch("/api/sketch/save", payload);
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error((data.errors ?? [`save: ${res.status}`]).join("; "));
  }
  return data.sketch;
}

export async function deleteSketch(sketchId: string): Promise<void> {
  const res = await postSketch("/api/sketch/delete", { sketch_id: sketchId });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error((data.errors ?? [`delete: ${res.status}`]).join("; "));
  }
}

export async function fetchSketches(): Promise<SketchRecord[]> {
  const res = await fetch(`${BASE}/api/sketches`);
  if (!res.ok) throw new Error(`sketches: ${res.status}`);
  const data = await res.json();
  return data.sketches ?? [];
}

export async function downloadSketchMidi(payload: SketchPayload): Promise<Blob> {
  const res = await postSketch("/api/sketch/midi", payload);
  if (!res.ok) {
    let message = `midi: ${res.status}`;
    try {
      const data = await res.json();
      if (data.errors) message = data.errors.join("; ");
    } catch {
      // non-JSON error body
    }
    throw new Error(message);
  }
  return res.blob();
}
