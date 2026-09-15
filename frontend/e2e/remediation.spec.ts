import { expect, test, type APIResponse, type Page } from "@playwright/test";

import { loginAsAdmin } from "./helpers/auth";

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

async function bestEffortDelete(page: Page, url: string): Promise<void> {
  await page.request.delete(url).catch(() => null);
}

function suffixFor(name: string): string {
  return `${name}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

// Minimal one-page PDF with extractable text (shared with workspace.spec.ts).
const RESUME_PDF = Buffer.from(
  "JVBERi0xLjMKJenr8b8KMSAwIG9iago8PAovQ291bnQgMQovS2lkcyBbMyAwIFJdCi9NZWRpYUJveCBbMCAwIDU5NS4yOCA4NDEuODldCi9UeXBlIC9QYWdlcwo+PgplbmRvYmoKMiAwIG9iago8PAovT3BlbkFjdGlvbiBbMyAwIFIgL0ZpdEggbnVsbF0KL1BhZ2VMYXlvdXQgL09uZUNvbHVtbgovUGFnZXMgMSAwIFIKL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDQgMCBSCi9QYXJlbnQgMSAwIFIKL1Jlc291cmNlcyA2IDAgUgovVHlwZSAvUGFnZQo+PgplbmRvYmoKNCAwIG9iago8PAovRmlsdGVyIC9GbGF0ZURlY29kZQovTGVuZ3RoIDIzNQo+PgpzdHJlYW0KeJxtjstOwzAURPf9ilmCFJk8KG67oyKVKCwC5Aec+DZxm/hGtkPJ31NaCQmV3Wg0OnNSbGexmEscZ+sSd5sESSriGOUOeflTZYlIFpDLuZASpcZNnuZ4Jz/2dIty/3f1IMV9el4VnQo7dj1y2xhL5HA0oUUxhZZthI3y4bF4jlCwD42jj7fXCE9cH8hFeBkrcpYCeXF9kS1FvLiIfA3kDNmaVliPpgs4EX0ErXxbsXL6lJXV0DR0PPVkAwYzUHfS+Q+cxEJmF3fHe6qDX2HLFbTxNX+Sm+CUPRjbnKFqDNyrYNj+or4BsGhiIQplbmRzdHJlYW0KZW5kb2JqCjUgMCBvYmoKPDwKL0Jhc2VGb250IC9IZWx2ZXRpY2EKL0VuY29kaW5nIC9XaW5BbnNpRW5jb2RpbmcKL1N1YnR5cGUgL1R5cGUxCi9UeXBlIC9Gb250Cj4+CmVuZG9iago2IDAgb2JqCjw8Ci9Gb250IDw8L0YxIDUgMCBSPj4KL1Byb2NTZXQgWy9QREYgL1RleHQgL0ltYWdlQiAvSW1hZ2VDIC9JbWFnZUldCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9DcmVhdGlvbkRhdGUgKEQ6MjAyNjA3MDYxMjA3MTJaKQo+PgplbmRvYmoKeHJlZgowIDgKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE1IDAwMDAwIG4gCjAwMDAwMDAxMDIgMDAwMDAgbiAKMDAwMDAwMDIwNSAwMDAwMCBuIAowMDAwMDAwMjg1IDAwMDAwIG4gCjAwMDAwMDA1OTIgMDAwMDAgbiAKMDAwMDAwMDY4OSAwMDAwMCBuIAowMDAwMDAwNzc2IDAwMDAwIG4gCnRyYWlsZXIKPDwKL1NpemUgOAovUm9vdCAyIDAgUgovSW5mbyA3IDAgUgovSUQgWzw1MUVENTA2NDFBRkNEMTQ2N0NGNzQzQzU0MTM5NTdCOT48NTFFRDUwNjQxQUZDRDE0NjdDRjc0M0M1NDEzOTU3Qjk+XQo+PgpzdGFydHhyZWYKODMxCiUlRU9GCg==",
  "base64",
);

async function uploadResume(page: Page, name: string): Promise<Json> {
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
  await patch(page, `/api/resumes/${created.id}`, { title: name });
  return created;
}

async function createJob(page: Page, suffix: string, overrides: Json = {}): Promise<Json> {
  return post(page, "/api/jobs", {
    title: `Remediation Engineer ${suffix}`,
    company_name: `Remediation Co ${suffix}`,
    location: "Remote",
    work_mode: "remote",
    source: "company_site",
    source_url: `https://example.com/remediation-${suffix}`,
    description: "Build Python, FastAPI, and PostgreSQL services with Docker.",
    ...overrides,
  });
}

test.describe("remediated business workflows", () => {
  test("job detail toggles Track application to View tracker", async ({ page }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("track");
    const job = await createJob(page, suffix);
    const created: string[] = [job.id as string];

    try {
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
    } finally {
      for (const id of created) await bestEffortDelete(page, `/api/jobs/${id}`);
    }
  });

  test("material selectors keep resume and cover letter coherent", async ({ page }) => {
    test.setTimeout(90_000);
    await loginAsAdmin(page);
    const suffix = suffixFor("letters");
    const job = await createJob(page, suffix);

    const resumeA = await uploadResume(page, `Resume A ${suffix}`);
    const resumeB = await uploadResume(page, `Resume B ${suffix}`);
    const letter = await post(page, "/api/cover-letters", {
      job_id: job.id,
      resume_id: resumeA.id,
      tone: "professional",
    });

    try {
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
    } finally {
      await bestEffortDelete(page, `/api/resumes/${resumeA.id}`);
      await bestEffortDelete(page, `/api/resumes/${resumeB.id}`);
      await bestEffortDelete(page, `/api/jobs/${job.id}`);
      void letter;
    }
  });

  test("applied_at is recorded once and survives later stages", async ({ page }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("applied-at");
    const job = await createJob(page, suffix);

    const application = await post(page, "/api/applications", {
      job_id: job.id,
      status: "saved",
    });
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

    await bestEffortDelete(page, `/api/applications/${application.id}`);
    await bestEffortDelete(page, `/api/jobs/${job.id}`);
  });

  test("material generation advances preparation without regressing interviews", async ({
    page,
  }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("stages");
    const job = await createJob(page, suffix);
    const resume = await uploadResume(page, `Stage Resume ${suffix}`);

    const application = await post(page, "/api/applications", {
      job_id: job.id,
      resume_id: resume.id,
      status: "saved",
    });

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

    await bestEffortDelete(page, `/api/applications/${application.id}`);
    await bestEffortDelete(page, `/api/resumes/${resume.id}`);
    await bestEffortDelete(page, `/api/jobs/${job.id}`);
  });

  test("dashboard applied count is cumulative from applied_at", async ({ page }) => {
    await loginAsAdmin(page);
    const suffix = suffixFor("dashboard");
    const job = await createJob(page, suffix);

    const before = await get(page, "/api/dashboard/summary");
    const application = await post(page, "/api/applications", {
      job_id: job.id,
      status: "applied",
    });
    const afterApplied = await get(page, "/api/dashboard/summary");
    expect(afterApplied.applied).toBe((before.applied as number) + 1);

    await patch(page, `/api/applications/${application.id}`, { status: "rejected" });
    const afterOutcome = await get(page, "/api/dashboard/summary");
    expect(afterOutcome.applied).toBe((before.applied as number) + 1);

    await page.goto("/dashboard");
    await expect(page.getByText("Applied", { exact: true }).first()).toBeVisible();

    await bestEffortDelete(page, `/api/applications/${application.id}`);
    await bestEffortDelete(page, `/api/jobs/${job.id}`);
  });

  test("duplicate job rejected and duplicate discovery save reuses the saved job", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await loginAsAdmin(page);
    const suffix = suffixFor("dupes");

    const first = await createJob(page, suffix);
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
    const savedAgain = await post(page, `/api/discovery/results/${resultId}/save`, {});
    expect(savedAgain.id).toBe(savedFirst.id);

    await bestEffortDelete(page, `/api/jobs/${first.id}`);
    await bestEffortDelete(page, `/api/jobs/${savedFirst.id}`);
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
});
