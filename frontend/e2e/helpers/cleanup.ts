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
        await this.page.request.delete(url).catch(() => null);
      });
    } else {
      this.teardowns.push(target);
    }
  }

  /** Idempotent teardown; safe to call after partial failures. */
  async run(): Promise<void> {
    for (const teardown of this.teardowns.reverse()) {
      await teardown().catch(() => null);
    }
    this.teardowns = [];
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
