import { expect, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@jobgoblin.local";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "goblin-demo-pass-123";

export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  const skip = page.getByRole("button", { name: "Skip for now" });
  if (await skip.isVisible().catch(() => false)) {
    await skip.click();
  }

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}
