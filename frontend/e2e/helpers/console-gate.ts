import { test as base, expect } from "@playwright/test";

/**
 * Console gate: fail a test if the browser logged error-level console messages
 * or uncaught page exceptions during the test. Extend this `test` instead of
 * importing from @playwright/test directly.
 */
const UNAUTHENTICATED_401 =
  /^Failed to load resource: the server responded with a status of 401/;

export function isAllowedConsoleError(text: string, testFile: string): boolean {
  // Only authentication-flow tests expect pre-session /auth/me and failed
  // sign-in requests. A 401 in any signed-in workflow is a regression.
  return testFile.endsWith("auth.spec.ts") && UNAUTHENTICATED_401.test(text);
}

export const test = base.extend<{ cleanConsole: void }>({
  cleanConsole: [
    async ({ page }, use, testInfo) => {
      const errors: string[] = [];
      page.on("console", (message) => {
        if (message.type() !== "error") return;
        const text = message.text();
        if (!isAllowedConsoleError(text, testInfo.file)) {
          errors.push(text);
        }
      });
      page.on("pageerror", (error) => errors.push(String(error)));
      await use();
      expect(errors, `unexpected console errors:\n${errors.join("\n")}`).toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
