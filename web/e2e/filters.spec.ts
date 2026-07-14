import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  // Load all samples by selecting first library
  await page.getByText("Pack A").click();
  // wait for sample table to populate
  await expect(page.getByText("kick_Am_120.wav")).toBeVisible({ timeout: 5000 });
});

const SEARCH_PLACEHOLDER = "Name, key, path, type";

test("search filters samples by name", async ({ page }) => {
  await page.getByPlaceholder(SEARCH_PLACEHOLDER).fill("bass");
  await expect(page.getByText("bass_loop_Cm_90.wav")).toBeVisible();
  await expect(page.getByText("kick_Am_120.wav")).not.toBeVisible();
});

test("clearing search restores all samples", async ({ page }) => {
  await page.getByPlaceholder(SEARCH_PLACEHOLDER).fill("bass");
  await expect(page.getByText("kick_Am_120.wav")).not.toBeVisible();
  await page.getByPlaceholder(SEARCH_PLACEHOLDER).fill("");
  await expect(page.getByText("kick_Am_120.wav")).toBeVisible();
});
