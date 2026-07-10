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
  await page.route("**/api/sample**", (route) =>
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
  await page.route("**/api/scan/delete", (route) =>
    route.fulfill({ json: { ok: true } }),
  );
  await page.route("**/api/reload", (route) =>
    route.fulfill({ json: { ok: true } }),
  );
  await page.route("**/api/review", (route) =>
    route.fulfill({ json: { ok: true } }),
  );
}
