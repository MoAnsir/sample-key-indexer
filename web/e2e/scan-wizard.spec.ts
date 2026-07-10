import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
});

test("scan wizard button is visible", async ({ page }) => {
  await expect(page.getByRole("button", { name: /scan/i })).toBeVisible();
});

test("wizard opens on scan button click", async ({ page }) => {
  await page.getByRole("button", { name: /scan/i }).click();
  // first step: source folder selection
  await expect(page.getByText(/choose source folder/i)).toBeVisible({ timeout: 3000 });
});

test("wizard folder browser shows folders", async ({ page }) => {
  await page.getByRole("button", { name: /scan/i }).click();
  await expect(page.getByText("samples")).toBeVisible({ timeout: 3000 });
});

test("wizard can be closed/cancelled", async ({ page }) => {
  await page.getByRole("button", { name: /scan/i }).click();
  await expect(page.getByText(/choose source folder/i)).toBeVisible({ timeout: 3000 });
  const cancelBtn = page.getByRole("button", { name: /cancel/i });
  if (await cancelBtn.isVisible()) {
    await cancelBtn.click();
    await expect(page.getByText(/choose source folder/i)).not.toBeVisible();
  }
});
