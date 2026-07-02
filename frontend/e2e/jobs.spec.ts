import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers/auth";

test.describe("jobs", () => {
  test("admin can create and open a saved job", async ({ page }) => {
    await loginAsAdmin(page);
    await page.getByRole("link", { name: /Jobs/ }).click();
    await expect(page.getByRole("heading", { name: "Jobs" })).toBeVisible();

    await page.getByRole("button", { name: "Add job" }).click();
    await page.getByLabel("Role title").fill("Senior Platform Engineer");
    await page.getByLabel("Company").fill("E2E Systems");
    await page.getByLabel("Location").fill("Remote");
    await page.getByLabel("Work mode").selectOption("remote");
    await page.getByLabel("Priority").selectOption("high");
    await page.getByLabel("Source").selectOption("company_site");
    await page
      .getByLabel("Job description")
      .fill("Build FastAPI services, PostgreSQL data flows, and production dashboards.");
    await page.getByRole("button", { name: "Save job" }).click();

    await expect(page.getByText("Senior Platform Engineer")).toBeVisible();
    await expect(page.getByText("E2E Systems")).toBeVisible();

    await page.getByRole("link", { name: /Senior Platform Engineer/ }).click();
    await expect(page.getByRole("heading", { name: "Senior Platform Engineer" })).toBeVisible();
    await expect(page.getByText("Build FastAPI services")).toBeVisible();
    await expect(page.getByText("Resume analysis")).toBeVisible();
  });
});
