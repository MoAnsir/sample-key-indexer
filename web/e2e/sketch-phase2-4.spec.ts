/**
 * E2E tests for sketch Phases 2–4:
 *   Phase 2 — MIDI import + sketch editing
 *   Phase 3 — Arrangement engine
 *   Phase 4 — Cross-match (Find Matching Samples)
 *
 * All API calls are mocked via page.route() — no Python backend needed.
 */
import { test, expect } from "@playwright/test";
import { mockApi, mockApiWithSketches } from "./fixtures";
import path from "path";
import fs from "fs";
import os from "os";

// ---------------------------------------------------------------------------
// Shared mock helpers
// ---------------------------------------------------------------------------

async function mockPhase2Routes(page: import("@playwright/test").Page) {
  // Single-sketch fetch (edit flow)
  await page.route("**/api/sketch**", (route, request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/sketch" && request.method() === "GET") {
      return route.fulfill({
        json: {
          sketch: {
            sketch_id: "sk_e2e",
            name: "MPC bass idea",
            tonic: "D#",
            mode: "minor",
            bpm: 140,
            bars: 4,
            beats_per_bar: 4,
            type: "Bass",
            frequency_register: "low",
            note_events: [
              { note: 51, midi: 51, start: 0, duration: 1, velocity: 100 },
              { note: 55, midi: 55, start: 1, duration: 0.5, velocity: 90 },
            ],
            library_id: "sketches",
            source_kind: "sketch",
          },
        },
      });
    }
    return route.fallback();
  });

  // MIDI import
  await page.route("**/api/sketch/import-midi", (route) =>
    route.fulfill({
      json: {
        ok: true,
        sketch: {
          bpm: 95,
          bars: 2,
          beats_per_bar: 4,
          note_events: [{ note: 60, midi: 60, start: 0, duration: 1, velocity: 80 }],
          tonic: null, mode: null, type: null, name: null, frequency_register: null,
        },
      },
    }),
  );
}

async function mockPhase3Routes(page: import("@playwright/test").Page) {
  await page.route("**/api/sketch/arrangement", (route, request) => {
    if (request.url().includes("arrangement-midi")) return route.fallback();
    return route.fulfill({
      json: {
        ok: true,
        arrangement: {
          sections: [
            { label: "A", bar_start: 0, bar_end: 8, variation: "original", note_events: [{ midi: 51, start: 0, duration: 1, velocity: 100 }] },
            { label: "B", bar_start: 8, bar_end: 16, variation: "transpose_4th", note_events: [{ midi: 56, start: 32, duration: 1, velocity: 100 }] },
          ],
          total_bars: 16,
          bpm: 140,
          beats_per_bar: 4,
          tonic: "D#",
          mode: "minor",
        },
      },
    });
  });

  await page.route("**/api/sketch/arrangement-midi", (route) =>
    route.fulfill({
      body: Buffer.from([0x4d, 0x54, 0x68, 0x64]),
      headers: { "Content-Type": "audio/midi" },
    }),
  );
}

async function mockPhase4Routes(page: import("@playwright/test").Page) {
  await page.route("**/api/sketch/match", (route) =>
    route.fulfill({
      json: {
        ok: true,
        matches: [
          {
            id: 1, name: "bass_loop_Cm_90.wav", key: "C_minor", bpm: 90,
            type: "Bass", library_name: "Pack A", playback_status: "available",
            score: 0.75, match_reasons: ["same key", "fills lows"],
            source_kind: "audio",
          },
          {
            id: 2, name: "kick_Am_120.wav", key: "A_minor", bpm: 120,
            type: "Kick", library_name: "Pack A", playback_status: "available",
            score: 0.3, match_reasons: ["near same BPM"],
            source_kind: "audio",
          },
        ],
        total_searched: 3,
      },
    }),
  );
}

// Navigate to results step with a sketch and at least one note entered
async function goToResults(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "✏ New Sketch" }).click();
  await page.getByRole("button", { name: "Next: Notes" }).click();
  await page.getByTestId("roll-grid").click({ position: { x: 30, y: 30 } });
  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(page.getByText("3 · Analysis")).toBeVisible();
}

// ---------------------------------------------------------------------------
// Phase 2 — MIDI import
// ---------------------------------------------------------------------------

test.describe("Phase 2 — MIDI import", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await mockPhase2Routes(page);
    await page.goto("/");
  });

  test("MIDI import zone is visible on the notes step", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Next: Notes" }).click();
    await expect(page.getByText(/drop an mpc midi export/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /browse/i })).toBeVisible();
  });

  test("uploading a MIDI file pre-fills BPM from the import response", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Next: Notes" }).click();

    // Write a tiny temp file to upload
    const tmpFile = path.join(os.tmpdir(), "test.mid");
    fs.writeFileSync(tmpFile, Buffer.from([0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6]));

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(tmpFile);

    // Server returns bpm: 95 — summary text shows it
    await expect(page.getByText(/95 bpm/i)).toBeVisible();
    fs.unlinkSync(tmpFile);
  });

  test("MIDI import request is sent to the correct endpoint", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Next: Notes" }).click();

    const importRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/import-midi") && req.method() === "POST",
    );

    const tmpFile = path.join(os.tmpdir(), "test.mid");
    fs.writeFileSync(tmpFile, Buffer.from([0x4d, 0x54, 0x68, 0x64]));
    await page.locator('input[type="file"]').setInputFiles(tmpFile);
    await importRequest;
    fs.unlinkSync(tmpFile);
  });
});

// ---------------------------------------------------------------------------
// Phase 2 — Sketch editing
// ---------------------------------------------------------------------------

test.describe("Phase 2 — sketch edit flow", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiWithSketches(page);
    await mockPhase2Routes(page);
    await page.goto("/");
  });

  test("Edit button appears on sketch table rows", async ({ page }) => {
    await page.getByRole("heading", { name: "Sketches" }).click();
    await expect(page.getByTitle("Edit this sketch")).toBeVisible();
  });

  test("clicking Edit opens the wizard on the notes step with correct title", async ({ page }) => {
    await page.getByRole("heading", { name: "Sketches" }).click();
    await page.getByTitle("Edit this sketch").click();
    // The current step heading shows "Edit Notes"
    await expect(page.getByRole("heading", { name: "Edit Notes" })).toBeVisible();
    // The details form's Name input is not visible (we are on the notes step)
    await expect(page.getByLabel(/^name$/i)).not.toBeVisible();
  });

  test("editing an existing sketch sends Update Sketch as the save label", async ({ page }) => {
    await page.getByRole("heading", { name: "Sketches" }).click();
    await page.getByTitle("Edit this sketch").click();
    await expect(page.getByText("Edit Notes")).toBeVisible();
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByRole("button", { name: "Update Sketch" })).toBeVisible();
  });

  test("edit wizard sends sketch_id in the save payload", async ({ page }) => {
    await page.getByRole("heading", { name: "Sketches" }).click();
    await page.getByTitle("Edit this sketch").click();
    await page.getByRole("button", { name: "Analyze" }).click();

    const saveRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/save") && req.method() === "POST",
    );
    await page.getByRole("button", { name: "Update Sketch" }).click();
    const req = await saveRequest;
    const body = JSON.parse(req.postData() ?? "{}");
    expect(body.sketch_id).toBe("sk_e2e");
  });
});

// ---------------------------------------------------------------------------
// Phase 3 — Arrangement engine
// ---------------------------------------------------------------------------

test.describe("Phase 3 — arrangement engine", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await mockPhase3Routes(page);
    await page.goto("/");
  });

  test("Arrangement Engine section is visible on the results step after adding notes", async ({ page }) => {
    await goToResults(page);
    await expect(page.getByText("Arrangement Engine")).toBeVisible();
  });

  test("Arrangement Engine is NOT shown when no notes were entered", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByText("3 · Analysis")).toBeVisible();
    await expect(page.getByText("Arrangement Engine")).not.toBeVisible();
  });

  test("Build Arrangement sends a request and shows section chips", async ({ page }) => {
    await goToResults(page);
    const arrangementRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/arrangement") && !req.url().includes("midi") && req.method() === "POST",
    );
    await page.getByRole("button", { name: "Build Arrangement" }).click();
    // Wait for the request — verifies the endpoint is called
    await arrangementRequest;
    // Download button appears once arrangement data lands
    await expect(page.getByRole("button", { name: /download arrangement midi/i })).toBeVisible({ timeout: 10000 });
  });

  test("target bar selector changes the request payload", async ({ page }) => {
    await goToResults(page);
    await page.getByRole("button", { name: "32 bars" }).click();

    const arrangementRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/arrangement") && req.method() === "POST",
    );
    await page.getByRole("button", { name: "Build Arrangement" }).click();
    const req = await arrangementRequest;
    const body = JSON.parse(req.postData() ?? "{}");
    expect(body.target_bars).toBe(32);
  });

  test("strategy toggles appear and can be deselected", async ({ page }) => {
    await goToResults(page);
    await expect(page.getByRole("button", { name: "Humanize" })).toBeVisible();
    await expect(page.getByRole("button", { name: "A/B Sections" })).toBeVisible();
    await page.getByRole("button", { name: "Humanize" }).click();
    // After deselecting, strategy should not be included in request
    const req = page.waitForRequest((r) => r.url().includes("/api/sketch/arrangement"));
    await page.getByRole("button", { name: "Build Arrangement" }).click();
    const r = await req;
    const body = JSON.parse(r.postData() ?? "{}");
    expect(body.strategies).not.toContain("humanize");
  });

  test("Download Arrangement MIDI button appears after building", async ({ page }) => {
    await goToResults(page);
    await page.getByRole("button", { name: "Build Arrangement" }).click();
    await expect(page.getByRole("button", { name: /download arrangement midi/i })).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Phase 4 — Cross-match
// ---------------------------------------------------------------------------

test.describe("Phase 4 — find matching samples", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await mockPhase4Routes(page);
    await page.goto("/");
  });

  test("Find Matching Samples section is always visible on results step", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    // Use the section heading (h3) to avoid matching the button with the same label
    await expect(page.getByRole("heading", { name: "Find Matching Samples" })).toBeVisible();
  });

  test("shows a prompt when no library is loaded", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByText(/load a library from the dashboard/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /find matching samples/i })).toBeDisabled();
  });

  test("Find Matching Samples button is enabled after loading a library", async ({ page }) => {
    // Load a library first so samples are in store
    await page.getByText("Pack A").click();
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByRole("button", { name: /find matching samples/i })).toBeEnabled();
  });

  test("clicking Find Matching Samples sends the request and shows results", async ({ page }) => {
    await page.getByText("Pack A").click();
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();

    const matchRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/match") && req.method() === "POST",
    );
    await page.getByRole("button", { name: /find matching samples/i }).click();
    await matchRequest;

    await expect(page.getByText("bass_loop_Cm_90.wav")).toBeVisible();
    // Reason chips use lowercase; "Same key" in compatible-keys list uses title case
    await expect(page.getByText("same key", { exact: true })).toBeVisible();
    await expect(page.getByText("fills lows", { exact: true })).toBeVisible();
  });

  test("results show score badge and reason chips", async ({ page }) => {
    await page.getByText("Pack A").click();
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    await page.getByRole("button", { name: /find matching samples/i }).click();
    await expect(page.getByText("75%")).toBeVisible();
    await expect(page.getByText("same key", { exact: true })).toBeVisible();
  });

  test("dimension toggles change the request filters", async ({ page }) => {
    await page.getByText("Pack A").click();
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();

    // Deselect BPM filter
    await page.getByRole("button", { name: "BPM" }).click();

    const matchRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/match") && req.method() === "POST",
    );
    await page.getByRole("button", { name: /find matching samples/i }).click();
    const req = await matchRequest;
    const body = JSON.parse(req.postData() ?? "{}");
    expect(body.filters.bpm).toBe(false);
  });

  test("total searched count is shown", async ({ page }) => {
    await page.getByText("Pack A").click();
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    await page.getByRole("button", { name: /find matching samples/i }).click();
    // Mock returns total_searched: 3
    await expect(page.getByText(/from 3 samples/i)).toBeVisible();
  });
});
