import { Page } from "@playwright/test";

/** Intercept all API calls with mock data so e2e tests run without a Python backend. */
export async function mockApi(page: Page) {
  const catalog = {
    total: 3,
    index_paths: ["/data/lib_1.sqlite"],
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

  const samples = [
    {
      id: 1, name: "kick_Am_120.wav", file_path: "/s/kick_Am_120.wav",
      key: "A_minor", root_note: "A", type: "Kick", category: "OneShots",
      bpm: 120, confidence: 0.91, needs_review: false, reviewed: false,
      review_reasons: [], library_id: "lib_1", library_name: "Pack A",
      playback_status: "available", duration: 0.8,
    },
    {
      id: 2, name: "bass_loop_Cm_90.wav", file_path: "/s/bass_loop_Cm_90.wav",
      key: "C_minor", root_note: "C", type: "Bass", category: "Loops",
      bpm: 90, confidence: 0.45, needs_review: true, reviewed: false,
      review_reasons: ["low_confidence", "engine_key_disagreement"],
      library_id: "lib_1", library_name: "Pack A",
      playback_status: "available", duration: 4.0,
    },
    {
      id: 3, name: "pad_Em_reviewed.wav", file_path: "/s/pad_Em_reviewed.wav",
      key: "E_minor", root_note: "E", type: "Pads", category: "Loops",
      bpm: 0, confidence: 0.72, needs_review: true, reviewed: true,
      review_reasons: ["filename_key_disagreement"],
      library_id: "lib_2", library_name: "Pack B",
      playback_status: "missing", duration: 8.0,
    },
  ];

  await page.route("**/api/catalog", (route) =>
    route.fulfill({ json: catalog }),
  );
  await page.route("**/api/samples**", (route) =>
    route.fulfill({ json: { total: 3, offset: 0, limit: 15000, returned: 3, samples } }),
  );
  // Regex with \? so this doesn't also swallow /api/samples requests.
  await page.route(/\/api\/sample\?/, (route) =>
    route.fulfill({ json: { sample: samples[1] } }),
  );
  await page.route("**/api/browse-folders**", (route) =>
    route.fulfill({
      json: { path: "/", parent: null, folders: [{ name: "samples", path: "/samples" }] },
    }),
  );
  await page.route("**/api/scan/start", (route) =>
    route.fulfill({ json: { job_id: "job_test" } }),
  );
  await page.route("**/api/scan/status**", (route) =>
    route.fulfill({
      json: {
        job_id: "job_test", status: "completed", phase: "done",
        progress: 100, total: 10, log_tail: [], index_path: "/data/new.sqlite",
      },
    }),
  );
  await page.route("**/api/scan/delete-data", (route) =>
    route.fulfill({ json: { deleted: [], errors: [] } }),
  );
  await page.route("**/api/reload", (route) =>
    route.fulfill({ json: { ok: true } }),
  );
  await page.route("**/api/review", (route) =>
    route.fulfill({ json: { ok: true } }),
  );

  // Sketch endpoints
  const sketchContext = {
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
        { label: "Same key", key: "D#_minor", scale: "D# minor", notes: [], chords: ["D#m", "Fdim"] },
        { label: "Relative key", key: "F#_major", scale: "F# major", notes: [], chords: ["F#", "G#m"] },
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
  };

  await page.route("**/api/sketch/analyze", (route) =>
    route.fulfill({
      json: {
        ok: true,
        sketch: { name: "MPC bass idea" },
        sample: { key: "D#_minor", source_kind: "sketch" },
        context: sketchContext,
        out_of_scale_notes: [],
      },
    }),
  );

  await page.route("**/api/sketch/save", (route) =>
    route.fulfill({
      json: {
        ok: true,
        sketch: {
          sketch_id: "sk_e2e",
          name: "MPC bass idea",
          key: "D#_minor",
          bpm: 140,
          type: "Bass",
          library_id: "sketches",
          source_kind: "sketch",
          created_at: "2026-07-14T00:00:00+00:00",
        },
      },
    }),
  );

  await page.route("**/api/sketch/delete", (route) =>
    route.fulfill({ json: { ok: true } }),
  );

  await page.route("**/api/sketches", (route) =>
    route.fulfill({ json: { sketches: [] } }),
  );
}

/** Catalog + samples where a saved sketch library exists (for card/table tests). */
export async function mockApiWithSketches(page: Page) {
  await mockApi(page);

  const sketchSample = {
    id: 10, name: "MPC bass idea", file_path: "sketch://sk_e2e",
    key: "D#_minor", root_note: "D#", type: "Bass", category: "OneShots",
    bpm: 140, confidence: 1.0, needs_review: false, reviewed: false,
    review_reasons: [], library_id: "sketches", library_name: "Sketches",
    playback_status: "sketch", source_kind: "sketch", sketch_id: "sk_e2e",
    duration: 13.7,
  };

  // Later registrations take precedence in Playwright routing.
  await page.route("**/api/catalog", (route) =>
    route.fulfill({
      json: {
        total: 1,
        index_paths: ["/home/user/.sample-key-indexer/sketches.sqlite"],
        stats: [{ type: "Bass", count: 1, percentage: 100 }],
        libraries: [
          {
            id: "sketches",
            name: "Sketches",
            total: 1,
            available: 0,
            missing: 1,
            available_percentage: 0,
            sources: [],
            index_paths: ["/home/user/.sample-key-indexer/sketches.sqlite"],
          },
        ],
      },
    }),
  );
  await page.route("**/api/samples**", (route) =>
    route.fulfill({
      json: { total: 1, offset: 0, limit: 15000, returned: 1, samples: [sketchSample] },
    }),
  );
}
