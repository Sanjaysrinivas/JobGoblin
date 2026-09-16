import { expect, test, type APIResponse, type Page } from "@playwright/test";

import { loginAsAdmin } from "./helpers/auth";
import { type Cleanup, withCleanup } from "./helpers/cleanup";
import { RESUME_PDF } from "./helpers/fixtures";

type Json = Record<string, unknown>;

async function expectOk(response: APIResponse): Promise<Json> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as Json;
}

async function post(page: Page, url: string, data: unknown): Promise<Json> {
  return expectOk(await page.request.post(url, { data }));
}

async function patch(page: Page, url: string, data: unknown): Promise<Json> {
  return expectOk(await page.request.patch(url, { data }));
}

async function get(page: Page, url: string): Promise<Json> {
  return expectOk(await page.request.get(url));
}

function suffixFor(name: string): string {
  return `${name}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

// Minimal one-page PDF with extractable text (shared with workspace.spec.ts).

async function uploadResume(
  page: Page,
  cleanup: Cleanup,
  name: string
): Promise<Json> {
  const created = await expectOk(
    await page.request.post("/api/resumes/upload", {
      multipart: {
        file: {
          name: `${name}.pdf`,
          mimeType: "application/pdf",
          buffer: RESUME_PDF,
        },
      },
    })
  );
  cleanup.add(`/api/resumes/${created.id}`);
  await patch(page, `/api/resumes/${created.id}`, { title: name });
  return created;
}

async function createJob(
  page: Page,
  cleanup: Cleanup,
  suffix: string,
  overrides: Json = {}
): Promise<Json> {
  const job = await post(page, "/api/jobs", {
    title: `Remediation Engineer ${suffix}`,
    company_name: `Remediation Co ${suffix}`,
    location: "Remote",
    work_mode: "remote",
    source: "company_site",
    source_url: `https://example.com/remediation-${suffix}`,
    description: "Build Python, FastAPI, and PostgreSQL services with Docker.",
    ...overrides,
  });
  cleanup.add(`/api/jobs/${job.id}`);
  return job;
}

test.describe("remediated business workflows", () => {
  test("job detail toggles Track application to View tracker", async ({ page }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("track");

    await withCleanup(page, async (cleanup) => {
      const job = await createJob(page, cleanup, suffix);

      await page.goto(`/jobs/${job.id}`);
      const trackButton = page.getByRole("button", { name: "Track application" });
      await expect(trackButton).toBeVisible();
      await trackButton.click();
      await expect(
        page.getByRole("button", { name: "View tracker" })
      ).toBeVisible();

      // Tracked state survives a reload.
      await page.reload();
      await expect(
        page.getByRole("button", { name: "View tracker" })
      ).toBeVisible();

      // View tracker navigates to the applications page.
      await page.getByRole("button", { name: "View tracker" }).click();
      await expect(page).toHaveURL(/\/applications$/);
      await expect(
        page.getByText(`Remediation Engineer ${suffix}`).first()
      ).toBeVisible();
    });
  });

  test("material selectors keep resume and cover letter coherent", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAsAdmin(page);
    const suffix = suffixFor("letters");

    await withCleanup(page, async (cleanup) => {
      const job = await createJob(page, cleanup, suffix);
      const resumeA = await uploadResume(page, cleanup, `Resume A ${suffix}`);
      await uploadResume(page, cleanup, `Resume B ${suffix}`);
      await post(page, "/api/cover-letters", {
        job_id: job.id,
        resume_id: resumeA.id,
        tone: "professional",
      });

      await page.goto("/applications");
      await page.getByRole("button", { name: "Track application" }).click();
      await expect(page.getByText("Track a saved job")).toBeVisible();

      const jobSelect = page.locator("#application-job");
      await jobSelect.selectOption({ label: `${job.title} at ${job.company_name}` });

      // Cover-letter options are limited to the selected job's letters;
      // selecting one derives its linked resume.
      const letterSelect = page.locator("#application-cover-letter");
      const letterOptions = await letterSelect.locator("option").allTextContents();
      expect(letterOptions).toContain("Professional · Draft");
      await letterSelect.selectOption({ index: 1 });
      await expect(page.locator("#application-resume")).toHaveValue(
        resumeA.id as string
      );

      // Switching to a resume the letter is not linked to clears the letter.
      await page
        .locator("#application-resume")
        .selectOption({ label: `Resume B ${suffix}` });
      await expect(letterSelect).toHaveValue("");
    });
  });

  test("applied_at is recorded once and survives later stages", async ({ page }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("applied-at");

    await withCleanup(page, async (cleanup) => {
      const job = await createJob(page, cleanup, suffix);
      const application = await post(page, "/api/applications", {
        job_id: job.id,
        status: "saved",
      });
      cleanup.add(`/api/applications/${application.id}`);
      expect(application.applied_at).toBeNull();

      const applied = await patch(page, `/api/applications/${application.id}`, {
        status: "applied",
      });
      expect(applied.applied_at).toBeTruthy();
      const appliedAt = applied.applied_at as string;

      for (const status of ["technical_interview", "offer", "rejected"]) {
        const updated = await patch(page, `/api/applications/${application.id}`, {
          status,
        });
        expect(updated.applied_at).toBe(appliedAt);
      }
    });
  });

  test("material generation advances preparation without regressing interviews", async ({
    page,
  }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("stages");

    await withCleanup(page, async (cleanup) => {
      const job = await createJob(page, cleanup, suffix);
      const resume = await uploadResume(page, cleanup, `Stage Resume ${suffix}`);
      const application = await post(page, "/api/applications", {
        job_id: job.id,
        resume_id: resume.id,
        status: "saved",
      });
      cleanup.add(`/api/applications/${application.id}`);

      // Creating a cover letter links materials and advances preparation only.
      await post(page, "/api/cover-letters", {
        job_id: job.id,
        resume_id: resume.id,
        tone: "professional",
      });
      let current = await get(page, `/api/applications/${application.id}`);
      expect(current.status).toBe("cover_letter_created");

      // Once interviewing, further material links must not regress the status.
      current = await patch(page, `/api/applications/${application.id}`, {
        status: "technical_interview",
      });
      expect(current.status).toBe("technical_interview");
      const appliedAt = current.applied_at as string;
      expect(appliedAt).toBeTruthy();

      await post(page, "/api/cover-letters", {
        job_id: job.id,
        resume_id: resume.id,
        tone: "friendly",
      });
      current = await get(page, `/api/applications/${application.id}`);
      expect(current.status).toBe("technical_interview");
      expect(current.applied_at).toBe(appliedAt);
    });
  });

  test("dashboard applied count is cumulative from applied_at", async ({ page }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("dashboard");

    await withCleanup(page, async (cleanup) => {
      const job = await createJob(page, cleanup, suffix);
      const before = await get(page, "/api/dashboard/summary");
      const application = await post(page, "/api/applications", {
        job_id: job.id,
        status: "applied",
      });
      cleanup.add(`/api/applications/${application.id}`);

      const afterApplied = await get(page, "/api/dashboard/summary");
      expect(afterApplied.applied).toBe((before.applied as number) + 1);

      await patch(page, `/api/applications/${application.id}`, { status: "rejected" });
      const afterOutcome = await get(page, "/api/dashboard/summary");
      expect(afterOutcome.applied).toBe((before.applied as number) + 1);

      await page.goto("/dashboard");
      await expect(page.getByText("Applied", { exact: true }).first()).toBeVisible();
    });
  });

  test("duplicate job rejected and duplicate discovery save reuses the saved job", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await loginAsAdmin(page);
    const suffix = suffixFor("dupes");

    await withCleanup(page, async (cleanup) => {
      const first = await createJob(page, cleanup, suffix);
      const duplicateResponse = await page.request.post("/api/jobs", {
        data: {
          title: `Remediation Engineer ${suffix}`,
          company_name: `Remediation Co ${suffix}`,
          location: "Remote",
          work_mode: "remote",
          source: "company_site",
          source_url: `https://example.com/remediation-${suffix}`,
          description: "Duplicate posting.",
        },
      });
      expect(duplicateResponse.status()).toBe(409);
      expect((await duplicateResponse.json()).code).toBe("job_exists");

      // Discovery: saving the same result twice returns the same saved job.
      // Discovery runs/results have no delete API — CI databases are
      // ephemeral; local runs are opt-in via E2E_ALLOW_MUTATION.
      await post(page, "/api/discovery/runs", {
        country: "us",
        query: "Backend Developer",
        results_per_page: 5,
      });
      const results = (await get(
        page,
        "/api/discovery/results?status=new"
      )) as unknown as Array<{ id: string }>;
      expect(results.length).toBeGreaterThan(0);
      const resultId = results[0].id;

      const savedFirst = await post(page, `/api/discovery/results/${resultId}/save`, {});
      cleanup.add(`/api/jobs/${savedFirst.id}`);
      const savedAgain = await post(page, `/api/discovery/results/${resultId}/save`, {});
      expect(savedAgain.id).toBe(savedFirst.id);
      void first;
    });
  });

  test("settings shows the account and configured providers", async ({ page }) => {
    await loginAsAdmin(page);

    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    const email = process.env.E2E_ADMIN_EMAIL ?? "admin@jobgoblin.local";
    await expect(page.getByLabel("Email")).toHaveValue(email);
    await expect(page.getByText("AI provider", { exact: true })).toBeVisible();
    await expect(page.getByText(/Provider:/).first()).toBeVisible();
  });

  test("run analysis analyzes the selected resume and records its breakdown", async ({
    page,
  }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("analysis");

    await withCleanup(page, async (cleanup) => {
      const job = await createJob(page, cleanup, suffix, {
        description:
          "Build backend services with Python, FastAPI, PostgreSQL, Docker, and Kubernetes.",
      });
      await uploadResume(page, cleanup, `Primary Resume ${suffix}`);
      const resumeB = await uploadResume(page, cleanup, `Other Resume ${suffix}`);

      await page.goto(`/jobs/${job.id}`);
      const resumeSelect = page.locator("#analysis-resume");
      await resumeSelect.selectOption(resumeB.id as string);
      await page.getByRole("button", { name: "Run analysis" }).click();
      await expect(page.getByText("Overall match")).toBeVisible();
      await expect(resumeSelect).toHaveValue(resumeB.id as string);

      // The run used resume B and recorded it in history; the stored
      // breakdown (F2) explains the score.
      const history = await page
        .locator("#analysis-history")
        .locator("option")
        .first()
        .textContent();
      expect(history).toContain(`Other Resume ${suffix}`);
    });
  });
});
