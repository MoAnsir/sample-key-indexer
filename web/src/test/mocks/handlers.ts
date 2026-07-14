import { http, HttpResponse } from "msw";
import type { CatalogResponse, Sample, SampleDetail } from "../../types/api";

// Test fixtures are intentionally partial — casts below keep them honest
// where it matters (fields the components actually read) without repeating
// every field of the full Sample/SampleDetail shapes.
export const MOCK_SAMPLES = [
  {
    id: 1,
    name: "kick_Am_120.wav",
    file_path: "/samples/kick_Am_120.wav",
    key: "A_minor",
    root_note: "A",
    type: "Kick",
    category: "OneShots",
    bpm: 120,
    confidence: 0.91,
    needs_review: false,
    reviewed: false,
    review_reasons: [],
    library_id: "lib_1",
    library_name: "Pack A",
    playback_status: "available",
    duration: 0.8,
  },
  {
    id: 2,
    name: "bass_loop_Cm_90.wav",
    file_path: "/samples/bass_loop_Cm_90.wav",
    key: "C_minor",
    root_note: "C",
    type: "Bass",
    category: "Loops",
    bpm: 90,
    confidence: 0.45,
    needs_review: true,
    reviewed: false,
    review_reasons: ["low_confidence", "engine_key_disagreement"],
    library_id: "lib_1",
    library_name: "Pack A",
    playback_status: "available",
    duration: 4.0,
  },
  {
    id: 3,
    name: "pad_Em_reviewed.wav",
    file_path: "/samples/pad_Em_reviewed.wav",
    key: "E_minor",
    root_note: "E",
    type: "Pads",
    category: "Loops",
    bpm: 0,
    confidence: 0.72,
    needs_review: true,
    reviewed: true,
    review_reasons: ["filename_key_disagreement"],
    library_id: "lib_2",
    library_name: "Pack B",
    playback_status: "missing",
    duration: 8.0,
  },
] as unknown as Sample[];

export const MOCK_CATALOG: CatalogResponse = {
  total: 3,
  index_paths: ["/data/lib_1.sqlite", "/data/lib_2.sqlite"],
  stats: [
    { type: "Kick", count: 1, percentage: 33.3 },
    { type: "Bass", count: 1, percentage: 33.3 },
    { type: "Pads", count: 1, percentage: 33.3 },
  ],
  libraries: [
    {
      id: "lib_1",
      name: "Pack A",
      total: 2,
      available: 2,
      missing: 0,
      available_percentage: 100,
      sources: [],
      index_paths: ["/data/lib_1.sqlite"],
    },
    {
      id: "lib_2",
      name: "Pack B",
      total: 1,
      available: 0,
      missing: 1,
      available_percentage: 0,
      sources: [],
      index_paths: ["/data/lib_2.sqlite"],
    },
  ],
};

export const MOCK_DETAIL = {
  ...MOCK_SAMPLES[1],
  key: "C_minor",
  root_note: "C",
  bpm: 90,
  confidence: 0.45,
  deep_key: "D_minor",
  deep_root: "D",
  deep_key_confidence: 0.51,
  deep_route_family: "librosa_yin",
  musical_record: {
    key: "C_minor",
    tonic: "C",
    mode: "minor",
    scale: "C minor",
    bpm: 90,
    tuning: 440,
    confidence: 0.48,
    notes: ["C", "D", "D#", "F", "G", "G#", "A#"],
  },
} as unknown as SampleDetail;

export const handlers = [
  http.get("/api/catalog", () => HttpResponse.json(MOCK_CATALOG)),

  http.get("/api/samples", () =>
    HttpResponse.json({
      total: MOCK_SAMPLES.length,
      offset: 0,
      limit: 15000,
      returned: MOCK_SAMPLES.length,
      samples: MOCK_SAMPLES,
    }),
  ),

  http.get("/api/sample", () => HttpResponse.json({ sample: MOCK_DETAIL })),

  http.post("/api/review", () => HttpResponse.json({ ok: true })),

  http.get("/api/browse-folders", () =>
    HttpResponse.json({
      path: "/",
      parent: null,
      folders: [
        { name: "samples", path: "/samples" },
        { name: "music", path: "/music" },
      ],
    }),
  ),

  http.post("/api/scan/start", () =>
    HttpResponse.json({ job_id: "job_abc123" }),
  ),

  http.get("/api/scan/status", () =>
    HttpResponse.json({
      job_id: "job_abc123",
      status: "completed",
      phase: "done",
      progress: 100,
      total: 10,
      log_tail: [],
      index_path: "/data/lib_new.sqlite",
    }),
  ),

  http.post("/api/scan/delete", () => HttpResponse.json({ ok: true })),

  http.post("/api/reload", () => HttpResponse.json({ ok: true })),

  http.post("/api/sketch/analyze", () => HttpResponse.json(MOCK_SKETCH_ANALYSIS)),

  http.post("/api/sketch/save", () =>
    HttpResponse.json({
      ok: true,
      sketch: {
        sketch_id: "sk_test123",
        name: "MPC bass idea",
        key: "D#_minor",
        bpm: 140,
        type: "Bass",
        library_id: "sketches",
        source_kind: "sketch",
        created_at: "2026-07-13T00:00:00+00:00",
      },
    }),
  ),

  http.post("/api/sketch/delete", () => HttpResponse.json({ ok: true })),

  http.get("/api/sketches", () => HttpResponse.json({ sketches: [] })),

  http.post("/api/sketch/match", () =>
    HttpResponse.json({
      ok: true,
      matches: [
        {
          id: 1,
          name: "bass_loop_Cm_90.wav",
          key: "C_minor",
          bpm: 90,
          type: "Bass",
          library_name: "Pack A",
          playback_status: "available",
          score: 0.8,
          match_reasons: ["same key", "fills lows"],
          source_kind: "audio",
        },
      ],
      total_searched: 3,
    }),
  ),

  http.post("/api/sketch/arrangement", () =>
    HttpResponse.json({
      ok: true,
      arrangement: {
        sections: [
          {
            label: "A",
            bar_start: 0,
            bar_end: 8,
            variation: "original",
            note_events: [{ midi: 48, start: 0, duration: 1, velocity: 100 }],
          },
          {
            label: "B",
            bar_start: 8,
            bar_end: 16,
            variation: "transpose_4th",
            note_events: [{ midi: 53, start: 32, duration: 1, velocity: 100 }],
          },
        ],
        total_bars: 16,
        bpm: 120,
        beats_per_bar: 4,
        tonic: "C",
        mode: "minor",
      },
    }),
  ),

  http.post("/api/sketch/arrangement-midi", () =>
    new HttpResponse(new Uint8Array([0x4d, 0x54, 0x68, 0x64]).buffer, {
      headers: { "Content-Type": "audio/midi" },
    }),
  ),

  http.get("/api/sketch", () =>
    HttpResponse.json({
      sketch: {
        sketch_id: "sk_test123",
        name: "Existing bass idea",
        tonic: "C",
        mode: "minor",
        bpm: 95,
        bars: 4,
        beats_per_bar: 4,
        type: "Bass",
        frequency_register: "low",
        note_events: [
          { note: 48, start: 0, duration: 1, velocity: 100 },
          { note: 51, start: 1, duration: 0.5, velocity: 90 },
        ],
        library_id: "sketches",
        source_kind: "sketch",
      },
    }),
  ),

  http.post("/api/sketch/import-midi", () =>
    HttpResponse.json({
      ok: true,
      sketch: {
        bpm: 120,
        bars: 2,
        beats_per_bar: 4,
        note_events: [{ note: 60, start: 0, duration: 1, velocity: 80 }],
        tonic: null,
        mode: null,
        type: null,
        name: null,
        frequency_register: null,
      },
    }),
  ),
];

export const MOCK_SKETCH_ANALYSIS = {
  ok: true,
  sketch: { name: "MPC bass idea", tonic: "D#", mode: "minor" },
  sample: { key: "D#_minor", source_kind: "sketch" },
  context: {
    musical_record: {
      tonic: "D#",
      mode: "minor",
      key: "D#_minor",
      scale: "D# minor",
      notes: ["D#", "F", "F#", "G#", "A#", "B", "C#"],
      chords: ["D#m", "F", "F#"],
      bpm: 140,
      confidence: 1.0,
    },
    compatibility: {
      keys: [
        { label: "Same key", key: "D#_minor", scale: "D# minor", notes: [], chords: [] },
        { label: "Relative key", key: "F#_major", scale: "F# major", notes: [], chords: [] },
      ],
      progressions: [
        {
          name: "Minor lift",
          mood: "dark",
          progression: ["D#m", "B", "F#"],
          roman: ["i", "VI", "III"],
          notes_to_play: ["D#", "B", "F#"],
        },
      ],
    },
    mood_profile: {
      primary: "dark",
      supporting: ["driving"],
      transitions: ["driving", "cinematic"],
      reasons: ["minor_mode"],
    },
    transition_suggestions: [
      { label: "driving", why: "dark material usually moves well into driving textures." },
    ],
  },
  out_of_scale_notes: [],
};
