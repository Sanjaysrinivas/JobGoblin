import type { APIResponse, Page } from "@playwright/test";

import { expect, test } from "./helpers/console-gate";
import { Cleanup, withCleanup } from "./helpers/cleanup";
import globalSetup from "./helpers/global-setup";

function pageWithDeletes(statuses: Record<string, number>, events: string[]): Page {
  return {
    request: {
      delete: async (url: string) => {
        events.push(`delete:${url}`);
        const status = statuses[url] ?? 204;
        return {
          ok: () => status >= 200 && status < 300,
          status: () => status,
        } as APIResponse;
      },
    },
  } as unknown as Page;
}

test("cleanup is reverse ordered, idempotent, and tolerates only 404", async () => {
  const events: string[] = [];
  const cleanup = new Cleanup(pageWithDeletes({ "/missing": 404 }, events));
  cleanup.add(async () => { events.push("first"); });
  cleanup.add("/missing");
  cleanup.add(async () => { events.push("last"); });

  await cleanup.run();
  await cleanup.run();

  expect(events).toEqual(["last", "delete:/missing", "first"]);
});

test("cleanup attempts every action and reports unexpected failures", async () => {
  const events: string[] = [];
  const cleanup = new Cleanup(pageWithDeletes({ "/broken": 500 }, events));
  cleanup.add(async () => { events.push("first"); });
  cleanup.add("/broken");
  cleanup.add(async () => {
    events.push("last");
    throw new Error("transport failed");
  });

  await expect(cleanup.run()).rejects.toThrow("2 E2E cleanup action(s) failed");
  expect(events).toEqual(["last", "delete:/broken", "first"]);
});

test("withCleanup tears resources down when the test body fails", async () => {
  const events: string[] = [];
  const page = pageWithDeletes({}, events);

  await expect(withCleanup(page, async (cleanup) => {
    cleanup.add("/created-resource");
    throw new Error("forced assertion failure");
  })).rejects.toThrow("forced assertion failure");

  expect(events).toEqual(["delete:/created-resource"]);
});

test("global setup refuses mutation without an explicit opt-in", async () => {
  const previous = process.env.E2E_ALLOW_MUTATION;
  try {
    delete process.env.E2E_ALLOW_MUTATION;
    await expect(globalSetup()).rejects.toThrow("E2E_ALLOW_MUTATION=true");
    process.env.E2E_ALLOW_MUTATION = "true";
    await expect(globalSetup()).resolves.toBeUndefined();
  } finally {
    if (previous === undefined) delete process.env.E2E_ALLOW_MUTATION;
    else process.env.E2E_ALLOW_MUTATION = previous;
  }
});
