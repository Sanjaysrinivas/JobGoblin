import { expect, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@jobgoblin.local";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "goblin-demo-pass-123";

export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  const skip = page.getByRole("button", { name: "Skip for now" });
  await Promise.race([
    page.waitForURL(/\/dashboard$/, { timeout: 10000 }).catch(() => null),
    skip.waitFor({ state: "visible", timeout: 10000 }).catch(() => null),
  ]);

  if (await skip.isVisible().catch(() => false)) {
    await Promise.all([
      page.waitForURL(/\/dashboard$/, { timeout: 10000 }),
      skip.click(),
    ]);
  }

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}
