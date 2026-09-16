import { expect, test, type APIResponse, type Page } from "@playwright/test";
import { loginAsAdmin } from "./helpers/auth";
import { type Cleanup, withCleanup } from "./helpers/cleanup";
import { RESUME_PDF } from "./helpers/fixtures";

async function expectOk<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as T;
}

async function post<T>(page: Page, url: string, data: unknown): Promise<T> {
  return expectOk<T>(await page.request.post(url, { data }));
}

async function get<T>(page: Page, url: string): Promise<T> {
  return expectOk<T>(await page.request.get(url));
}



test.describe("workspace workflows", () => {
  test("covers the main authenticated job-search loop", async ({ page }) => {
    test.setTimeout(120_000);
    await loginAsAdmin(page);

    const suffix = Date.now().toString(36);
    await withCleanup(page, async (cleanup: Cleanup) => {
      const resume = await expectOk<{ id: string; title: string; current_version_id: string | null }>(
        await page.request.post("/api/resumes/upload", {
          multipart: {
            file: {
              name: `e2e-resume-${suffix}.pdf`,
              mimeType: "application/pdf",
              buffer: RESUME_PDF,
            },
          },
        })
      );
      cleanup.add(`/api/resumes/${resume.id}`);
      await expectOk(await page.request.patch(`/api/resumes/${resume.id}`, {
        data: { is_default: true, title: `E2E Resume ${suffix}` },
      }));

      // The profile belongs to the shared admin account: restore it afterwards.
      const profileBefore = await get<Record<string, unknown>>(page, "/api/profile");
      cleanup.add(async () => {
        const fields = [
          "full_name", "headline", "location", "summary",
          "skills", "experience", "education", "projects", "certifications",
        ];
        const restore = Object.fromEntries(
          fields.filter((f) => profileBefore[f] !== undefined).map((f) => [f, profileBefore[f]])
        );
        await page.request.put("/api/profile", { data: restore }).catch(() => null);
      });
      await expectOk(await page.request.put("/api/profile", {
        data: {
          full_name: `E2E User ${suffix}`,
          headline: "Platform Engineer",
          location: "Remote",
          summary: "Builds FastAPI services and job discovery workflows.",
          skills: ["Python", "FastAPI", "PostgreSQL", "Kubernetes"],
          experience: [{ company: "E2E Systems", role: "Platform Engineer", start: "2022", end: null, highlights: ["Built API workflows"] }],
          education: [],
          projects: ["Job discovery ranking"],
          certifications: [],
        },
      }));

      const job = await post<{ id: string; title: string }>(page, "/api/jobs", {
        title: `Platform Engineer ${suffix}`,
        company_name: `E2E Co ${suffix}`,
        location: "Remote",
        work_mode: "remote",
        source: "company_site",
        source_url: `https://example.com/e2e-role-${suffix}`,
        description: "Build Python, FastAPI, PostgreSQL, Docker, and Kubernetes services.",
        priority: "high",
      });
      cleanup.add(`/api/jobs/${job.id}`);
      const contact = await post<{ id: string }>(page, "/api/contacts", {
        job_id: job.id,
        name: `Taylor Recruiter ${suffix}`,
        company: `E2E Co ${suffix}`,
        role: "Recruiter",
        email: `taylor-${suffix}@example.com`,
        notes: "Met through E2E smoke test.",
        contacted: true,
      });
      cleanup.add(`/api/contacts/${contact.id}`);
      const analysis = await post<{ id: string; overall_score: number }>(page, "/api/analysis/resume-job", {
        resume_id: resume.id,
        job_id: job.id,
      });
      const coverLetter = await post<{ id: string }>(page, "/api/cover-letters", {
        job_id: job.id,
        resume_id: resume.id,
        tone: "professional",
      });
      await post(page, `/api/jobs/${job.id}/resume-drafts`, {
        resume_id: resume.id,
        source_version_id: resume.current_version_id,
      });
      const application = await post<{ id: string }>(page, "/api/applications", {
        job_id: job.id,
        resume_id: resume.id,
        cover_letter_id: coverLetter.id,
        status: "applied",
        follow_up_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        notes: `Follow up from E2E ${suffix}`,
      });
      cleanup.add(`/api/applications/${application.id}`);
      await post(page, "/api/outreach", {
        job_id: job.id,
        contact_id: contact.id,
        channel: "email",
        message_type: "status_check",
        content: `Checking in on ${job.title}`,
        status: "draft",
      });
      await post(page, "/api/interview-prep", {
        job_id: job.id,
        application_id: application.id,
        resume_id: resume.id,
        resume_version_id: resume.current_version_id,
        notes: `Prep notes ${suffix}`,
      });

      await page.goto("/resumes");
    await expect(page.getByRole("heading", { name: "Resumes" })).toBeVisible();
    await expect(page.getByText(`E2E Resume ${suffix}`)).toBeVisible();

    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
    await expect(page.getByLabel("Full name")).toHaveValue(`E2E User ${suffix}`);
    await expect(page.getByLabel("Headline")).toHaveValue("Platform Engineer");

    await page.goto("/discover");
    await expect(page.getByRole("heading", { name: "Discover", exact: true })).toBeVisible();
    await page.getByLabel("Target region").selectOption("north_america");
    await page.getByLabel("Country").selectOption("us");
    await page.getByLabel("Job type").selectOption("it");
    await page.getByLabel("Role").selectOption("Backend Developer");
    await page.getByLabel("Work mode").selectOption("remote");
    await page.getByRole("button", { name: "Run search" }).click();
    await expect(page.getByText(/Found \d+ new result/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/match/).first()).toBeVisible();

    await page.goto("/jobs");
    await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
    await expect(page.getByRole("main").getByText(job.title).first()).toBeVisible();
    await page.goto(`/jobs/${job.id}`);
    await expect(page.getByRole("heading", { name: job.title, exact: true })).toBeVisible();
    await expect(page.getByText("Resume analysis")).toBeVisible();
    expect(analysis.overall_score).toBeGreaterThan(0);
    await expect(page.getByText("Overall match")).toBeVisible();
    await expect(page.getByText("Application readiness")).toBeVisible();
    await expect(page.getByText("Cover letters", { exact: true })).toBeVisible();
    await expect(page.getByText("AI resume editor", { exact: true })).toBeVisible();
    await expect(page.getByText("Interview prep", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Notes", exact: true })).toHaveValue(`Prep notes ${suffix}`);

    await page.goto("/contacts");
    await expect(page.getByRole("heading", { name: "Contacts" })).toBeVisible();
    await expect(page.getByText(`Taylor Recruiter ${suffix}`)).toBeVisible();

    await page.goto("/outreach");
    await expect(page.getByRole("heading", { name: "Outreach" })).toBeVisible();
    await expect(page.getByText("Status Check").first()).toBeVisible();
    await expect(page.getByText(`Checking in on ${job.title}`)).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy email" }).first()).toBeVisible();

    await page.goto("/applications");
    await expect(page.getByRole("heading", { name: "Applications" })).toBeVisible();
    await expect(page.getByRole("main").getByText(job.title).first()).toBeVisible();
    await page.getByRole("button", { name: "Workflow" }).first().click();
    await expect(page.getByText("Materials")).toBeVisible();
    await expect(page.getByText(`Taylor Recruiter ${suffix}`)).toBeVisible();
    await expect(page.getByText("Status Check - Draft")).toBeVisible();

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("Pipeline", { exact: true })).toBeVisible();
    await expect(page.getByText(`Started tracking ${job.title}`)).toBeVisible();

    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(page.getByText("AI provider", { exact: true })).toBeVisible();
    });
  });
});
