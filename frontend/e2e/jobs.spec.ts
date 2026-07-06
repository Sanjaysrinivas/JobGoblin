import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers/auth";

test.describe("jobs", () => {
  test("admin can create and open a saved job", async ({ page }) => {
    const suffix = Date.now().toString(36);
    const title = `Senior Platform Engineer ${suffix}`;
    const company = `E2E Systems ${suffix}`;
    await loginAsAdmin(page);
    await page.getByRole("link", { name: /Jobs/ }).click();
    await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Add a job", exact: true }).click();
    await page.getByLabel("Role title").fill(title);
    await page.getByLabel("Company").fill(company);
    await page.getByLabel("Location").fill("Remote");
    await page.getByLabel("Work mode").selectOption("remote");
    await page.getByLabel("Priority").selectOption("high");
    await page.getByLabel("Source", { exact: true }).selectOption("company_site");
    await page
      .getByLabel("Job description")
      .fill("Build FastAPI services, PostgreSQL data flows, and production dashboards.");
    await page.getByRole("button", { name: "Save job" }).click();

    await expect(page.getByText(title)).toBeVisible();
    await expect(page.getByText(company)).toBeVisible();

    await page.getByRole("link", { name: new RegExp(title) }).click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.getByText("Build FastAPI services")).toBeVisible();
    await expect(page.getByText("Resume analysis")).toBeVisible();
  });
});
