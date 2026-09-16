import type { Page } from "@playwright/test";

/**
 * Failure-safe resource cleanup for E2E tests. Every created resource is
 * registered immediately after creation; teardown runs from a finally block
 * in reverse dependency order (contacts, applications, jobs, resumes) and
 * tolerates 404s so retries after partial failures stay clean.
 *
 * Job deletion cascades cover letters, interview prep, and resume drafts.
 * Discovery runs/results have no delete API: they are ephemeral by policy —
 * CI destroys its database volume, and local runs require the explicit
 * E2E_ALLOW_MUTATION opt-in.
 */
type Teardown = () => Promise<void>;

export class Cleanup {
  private teardowns: Teardown[] = [];

  constructor(private readonly page: Page) {}

  /** Register a DELETE endpoint, or an arbitrary teardown action. */
  add(target: string | Teardown): void {
    if (typeof target === "string") {
      const url = target;
      this.teardowns.push(async () => {
        const response = await this.page.request.delete(url);
        if (!response.ok() && response.status() !== 404) {
          throw new Error(`DELETE ${url} failed with HTTP ${response.status()}`);
        }
      });
    } else {
      this.teardowns.push(target);
    }
  }

  /** Idempotent teardown; safe to call after partial failures. */
  async run(): Promise<void> {
    const failures: unknown[] = [];
    for (const teardown of this.teardowns.reverse()) {
      try {
        await teardown();
      } catch (error) {
        failures.push(error);
      }
    }
    this.teardowns = [];
    if (failures.length > 0) {
      throw new AggregateError(failures, `${failures.length} E2E cleanup action(s) failed`);
    }
  }
}

/** Run a test body with guaranteed teardown of everything it registered. */
export async function withCleanup(
  page: Page,
  body: (cleanup: Cleanup) => Promise<void>
): Promise<void> {
  const cleanup = new Cleanup(page);
  try {
    await body(cleanup);
  } finally {
    await cleanup.run();
  }
}
