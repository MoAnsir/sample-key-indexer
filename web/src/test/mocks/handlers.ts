import { http, HttpResponse } from "msw";
import type { CatalogResponse, Sample, SampleDetail } from "../../types/api";

export const MOCK_SAMPLES: Sample[] = [
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
];

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
      sources: [],
      index_paths: ["/data/lib_1.sqlite"],
    },
    {
      id: "lib_2",
      name: "Pack B",
      total: 1,
      available: 0,
      missing: 1,
      sources: [],
      index_paths: ["/data/lib_2.sqlite"],
    },
  ],
};

export const MOCK_DETAIL: SampleDetail = {
  ...MOCK_SAMPLES[1],
  key: "C_minor",
  root_note: "C",
  bpm: 90,
  confidence: 0.45,
  deep_key: "D_minor",
  deep_root: "D",
  deep_key_confidence: 0.51,
  deep_route_family: "librosa_yin",
  musical_record: { key: "C_minor", tonic: "C", confidence: 0.48, bpm: 90 },
};

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

  http.get("/api/sample", ({ request }) => {
    const id = Number(new URL(request.url).searchParams.get("id"));
    return HttpResponse.json({ sample: MOCK_DETAIL });
  }),

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
];
