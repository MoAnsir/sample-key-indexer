import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
});

test("scan wizard button is visible", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Scan from..." })).toBeVisible();
});

test("wizard opens on scan button click", async ({ page }) => {
  await page.getByRole("button", { name: "Scan from..." }).click();
  // first step: source folder selection
  await expect(page.getByText("Source folder")).toBeVisible({ timeout: 3000 });
});

test("wizard folder browser shows folders", async ({ page }) => {
  await page.getByRole("button", { name: "Scan from..." }).click();
  await page.getByRole("button", { name: "Browse..." }).click();
  // appears in both the Quick Access sidebar and the folder list
  await expect(page.getByRole("button", { name: "📁 samples", exact: true })).toBeVisible({ timeout: 3000 });
});

test("wizard can be closed", async ({ page }) => {
  await page.getByRole("button", { name: "Scan from..." }).click();
  await expect(page.getByText("Source folder")).toBeVisible({ timeout: 3000 });
  await page.getByRole("button", { name: "✕" }).click();
  await expect(page.getByText("Source folder")).not.toBeVisible();
});
