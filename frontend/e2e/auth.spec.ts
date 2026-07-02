import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers/auth";

test.describe("authentication", () => {
  test("redirects unauthenticated workspace users to login", async ({ page }) => {
    await page.goto("/dashboard");

    await expect(page).toHaveURL(/\/login\?next=%2Fdashboard$/);
    await expect(page.getByText("Welcome back")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
  });

  test("shows an error for invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("nobody@example.com");
    await page.getByLabel("Password", { exact: true }).fill("definitely-wrong");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Invalid email or password.")).toBeVisible();
  });

  test("admin can sign in and see the application shell", async ({ page }) => {
    await loginAsAdmin(page);

    await expect(page.getByRole("link", { name: /Jobs/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Outreach/ })).toBeVisible();
    await expect(page.getByText("Pipeline")).toBeVisible();
  });
});
