// Slim sample returned by GET /api/samples (list view)
export interface Sample {
  id: number;
  index_path: string;
  index_writable: boolean;
  library_id: string;
  library_name: string;
  library_root: string | null;
  name: string;
  file_path: string;
  relative_path: string | null;
  destination: string | null;
  playable_path: string;
  playback_status: "available" | "missing" | "sketch";
  playback_source: string;
  source_kind?: string | null;
  sketch_id?: string | null;
  format: string | null;
  duration: number | null;
  size: number | null;
  mtime: number | null;
  root_note: string | null;
  key: string | null;
  bpm: number | null;
  category: string | null;
  type: string | null;
  subtype: string | null;
  source: string | null;
  brightness: string | null;
  warmth: string | null;
  confidence: number | null;
  needs_review: boolean;
  review_reasons: string[];
  reviewed: boolean;
  reviewed_at: string | null;
  error: string | null;
}

// Full sample detail returned by GET /api/sample?id=N
export interface SampleDetail extends Sample {
  sample_rate: number | null;
  notes: string[];
  chords: string[];
  rms_db: number | null;
  peak_db: number | null;
  dynamic_range_db: number | null;
  spectral_centroid: number | null;
  fundamental_freq: number | null;
  spectral_bandwidth: number | null;
  rolloff: number | null;
  scale_confidence: number | null;
  mfcc: number[];
  deep_review: Record<string, unknown>;
  deep_analysis: Record<string, unknown>;
  deep_analysis_mode: string | null;
  deep_analysis_scope: string | null;
  deep_analysis_status: string | null;
  deep_route_family: string | null;
  deep_sample_type: string | null;
  deep_category: string | null;
  deep_route_reason: string | null;
  deep_tonal_backend: string | null;
  deep_chord_backend: string | null;
  deep_timing_backend: string | null;
  deep_tuning_backend: string | null;
  deep_note_backend: string | null;
  deep_should_detect_chords: boolean | null;
  deep_should_detect_tuning: boolean | null;
  deep_should_transcribe_notes: boolean | null;
  deep_key: string | null;
  deep_root: string | null;
  deep_key_confidence: number | null;
  deep_chords: string[];
  deep_chord_strengths: number[];
  deep_hpcp: number[];
  deep_tuning_hz: number | null;
  deep_chords_key: string | null;
  deep_chords_scale: string | null;
  deep_chords_changes_rate: number | null;
  deep_chords_number_rate: number | null;
  deep_bpm: number | null;
  deep_bpm_confidence: number | null;
  deep_ticks: number[];
  deep_bpm_estimates: number[];
  deep_bpm_intervals: number[];
  deep_onsets: number[];
  deep_onset_count: number | null;
  deep_timing_confidence: number | null;
  deep_note_events: NoteEvent[];
  deep_note_count: number | null;
  deep_note_confidence: number | null;
  // Musical context (added by build_musical_context)
  musical_record: MusicalRecord | null;
  compatibility: Compatibility | null;
  mood_profile: MoodProfile | null;
  transition_suggestions: TransitionSuggestion[];
}

export interface NoteEvent {
  start: number;
  end: number;
  pitch: number;
  velocity: number;
  note: string;
}

export interface MusicalRecord {
  key: string;
  tonic: string;
  mode: string;
  scale: string;
  bpm: number | null;
  tuning: number | null;
  confidence: number | null;
  notes: string[];
}

export interface Compatibility {
  keys: CompatibleKey[];
  progressions: Progression[];
}

export interface CompatibleKey {
  label: string;
  key: string;
  scale: string;
  notes: string[];
  scale_notes: string[];
  diatonic_chords: string[];
  chords: string[];
}

export interface Progression {
  name: string;
  numerals: string;
  progression: string[];
  play_order: string[];
  mood: string;
}

export interface MoodProfile {
  primary: string;
  supporting: string[];
  transitions: string[];
}

export interface TransitionSuggestion {
  label: string;
  why: string;
}

// Library summary from GET /api/catalog
export interface Library {
  id: string;
  name: string;
  total: number;
  available: number;
  missing: number;
  available_percentage: number;
  sources: PlaybackSource[];
  index_paths: string[];
}

export interface PlaybackSource {
  source: string;
  count: number;
}

export interface TypeStat {
  type: string;
  count: number;
  percentage: number;
}

// GET /api/catalog response
export interface CatalogResponse {
  index_paths: string[];
  total: number;
  stats: TypeStat[];
  libraries: Library[];
}
