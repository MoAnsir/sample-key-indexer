import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByText("Pack A")).toBeVisible();
});

test("remove library button is visible on cards", async ({ page }) => {
  const deleteButtons = page.getByText("Remove library & delete scan data");
  await expect(deleteButtons.first()).toBeVisible();
});

test("cancelling delete dialog leaves card intact", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.dismiss());
  await page.getByText("Remove library & delete scan data").first().click();
  await expect(page.getByText("Pack A")).toBeVisible();
});

test("confirming delete calls scan/delete and reload endpoints", async ({ page }) => {
  const deleteCalled = page.waitForRequest((req) =>
    req.url().includes("/api/scan/delete") && req.method() === "POST",
  );
  const reloadCalled = page.waitForRequest((req) =>
    req.url().includes("/api/reload"),
  );

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByText("Remove library & delete scan data").first().click();

  await deleteCalled;
  await reloadCalled;
});
