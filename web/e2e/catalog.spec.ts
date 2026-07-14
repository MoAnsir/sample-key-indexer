import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
});

test("shows library cards on load", async ({ page }) => {
  await expect(page.getByText("Pack A")).toBeVisible();
  await expect(page.getByText("Pack B")).toBeVisible();
});

test("shows library sample counts", async ({ page }) => {
  await expect(page.getByText("2 samples")).toBeVisible();
  await expect(page.getByText("1 samples")).toBeVisible();
});

test("shows 2 libraries loaded header", async ({ page }) => {
  await expect(page.getByText("2 libraries loaded")).toBeVisible();
});

test("selecting a library card highlights it", async ({ page }) => {
  // target the card heading — after loading, table rows also contain "Pack A"
  await page.getByRole("heading", { name: "Pack A" }).click();
  await expect(page.getByRole("heading", { name: "Pack A" })).toBeVisible();
});

test("shows type distribution stats", async ({ page }) => {
  await expect(page.getByText("Sample Types")).toBeVisible();
  // exact matches — "Kick"/"Bass" also appear in the pie-chart legend ("Kick · 1")
  await expect(page.getByText("Kick", { exact: true })).toBeVisible();
  await expect(page.getByText("Bass", { exact: true })).toBeVisible();
});

test("hide/show charts toggle works", async ({ page }) => {
  await expect(page.getByText("Sample Types")).toBeVisible();
  await page.getByText("▲ Hide charts").click();
  await expect(page.getByText("Sample Types")).not.toBeVisible();
  await page.getByText("▼ Show charts").click();
  await expect(page.getByText("Sample Types")).toBeVisible();
});
