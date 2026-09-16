import { test as base, expect } from "@playwright/test";

/**
 * Console gate: fail a test if the browser logged error-level console messages
 * or uncaught page exceptions during the test. Extend this `test` instead of
 * importing from @playwright/test directly.
 */
const ALLOWED_PATTERNS: RegExp[] = [
  // Unauthenticated flows are expected work: /auth/me probes and failed
  // sign-in attempts legitimately answer 401 before a session exists, and
  // the browser logs those failed resource loads as console errors.
  /^Failed to load resource: the server responded with a status of 401/,
];

export const test = base.extend<{ cleanConsole: void }>({
  cleanConsole: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("console", (message) => {
        if (message.type() !== "error") return;
        const text = message.text();
        if (!ALLOWED_PATTERNS.some((pattern) => pattern.test(text))) {
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
