import { test, expect } from "@playwright/test";
import { mockApi, mockApiWithSketches } from "./fixtures";

test.describe("sketch creation flow", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await page.goto("/");
  });

  test("New Sketch opens the full-page details step", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await expect(page.getByRole("heading", { name: "New Sketch" })).toBeVisible();
    // full page, not a popup: step indicator + back-to-library button visible
    await expect(page.getByText("1 · Details")).toBeVisible();
    await expect(page.getByRole("button", { name: "Back to library" })).toBeVisible();
    // dashboard content replaced
    await expect(page.getByText("Sample Types")).not.toBeVisible();
  });

  test("← Library returns to the dashboard", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Back to library" }).click();
    await expect(page.getByText("Sample Types")).toBeVisible();
  });

  test("details form has MPC-style key options", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    const keySelect = page.getByLabel("Key");
    await expect(keySelect.locator("option", { hasText: "D# / Eb" })).toHaveCount(1);
  });

  test("notes step shows the grid with steps-per-bar T.C. labels", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Next: Notes" }).click();
    await expect(page.getByText("2 · Notes")).toBeVisible();
    await expect(page.getByTestId("roll-grid")).toBeVisible();
    await expect(page.locator("option", { hasText: "1/16 · 16 steps/bar" })).toHaveCount(1);
    await expect(page.getByText("No notes yet")).toBeVisible();
  });

  test("pencil click adds a note and updates the count", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Next: Notes" }).click();
    const grid = page.getByTestId("roll-grid");
    await grid.click({ position: { x: 30, y: 30 } });
    await expect(page.getByText("1 note entered.")).toBeVisible();
  });

  test("analyze shows the full results view", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByText("3 · Analysis")).toBeVisible();
    await expect(page.getByText("D#_minor")).toBeVisible();
    await expect(page.getByText("Compatible Keys")).toBeVisible();
    await expect(page.getByText("Relative key")).toBeVisible();
    await expect(page.getByText("Progressions to Try")).toBeVisible();
    await expect(page.getByText("Minor lift")).toBeVisible();
    await expect(page.getByText("Mood & Transitions")).toBeVisible();
  });

  test("MIDI download button appears only when notes were entered", async ({ page }) => {
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    // no notes -> no MIDI button on results
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByText(/download your notes as midi/i)).not.toBeVisible();
    // add a note -> button appears
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await page.getByRole("button", { name: "Next: Notes" }).click();
    await page.getByTestId("roll-grid").click({ position: { x: 30, y: 30 } });
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(page.getByText(/download your notes as midi/i)).toBeVisible();
  });

  test("save persists and confirms", async ({ page }) => {
    const saveRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/save") && req.method() === "POST",
    );
    await page.getByRole("button", { name: "✏ New Sketch" }).click();
    await page.getByRole("button", { name: "Analyze" }).click();
    await page.getByRole("button", { name: "Save Sketch" }).click();
    await saveRequest;
    await expect(page.getByText(/sketch saved/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Done" })).toBeVisible();
  });
});

test.describe("saved sketches on the dashboard and table", () => {
  test.beforeEach(async ({ page }) => {
    await mockApiWithSketches(page);
    await page.goto("/");
  });

  test("sketches library renders as a sketch card", async ({ page }) => {
    const card = page.getByTestId("library-card-sketches");
    await expect(card).toBeVisible();
    await expect(card).toContainText("✏ Sketch");
    await expect(card).toContainText("1 sketch");
    await expect(card).toContainText("no audio files, MIDI only");
    await expect(card).not.toContainText("missing");
    await expect(card).not.toContainText("Remove library & delete scan data");
  });

  test("sketch rows show sketch badge with MIDI and delete actions", async ({ page }) => {
    await page.getByRole("heading", { name: "Sketches" }).click();
    await expect(page.getByText("MPC bass idea")).toBeVisible();
    await expect(page.getByRole("table").getByText("✏ Sketch")).toBeVisible();
    const midiLink = page.getByText("⬇ MIDI");
    await expect(midiLink).toHaveAttribute("href", "/api/sketch/midi?sketch_id=sk_e2e");
    await expect(page.getByTitle("Delete this sketch")).toBeVisible();
  });

  test("deleting a sketch removes the row", async ({ page }) => {
    await page.getByRole("heading", { name: "Sketches" }).click();
    await expect(page.getByText("MPC bass idea")).toBeVisible();
    page.on("dialog", (dialog) => dialog.accept());
    const deleteRequest = page.waitForRequest(
      (req) => req.url().includes("/api/sketch/delete") && req.method() === "POST",
    );
    await page.getByTitle("Delete this sketch").click();
    await deleteRequest;
    await expect(page.getByText("MPC bass idea")).not.toBeVisible();
  });
});
