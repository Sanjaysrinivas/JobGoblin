import { expect, test, type APIResponse, type Page } from "@playwright/test";
import { loginAsAdmin } from "./helpers/auth";

async function expectOk<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as T;
}

async function post<T>(page: Page, url: string, data: unknown): Promise<T> {
  return expectOk<T>(await page.request.post(url, { data }));
}

const RESUME_PDF = Buffer.from(
  "JVBERi0xLjMKJenr8b8KMSAwIG9iago8PAovQ291bnQgMQovS2lkcyBbMyAwIFJdCi9NZWRpYUJveCBbMCAwIDU5NS4yOCA4NDEuODldCi9UeXBlIC9QYWdlcwo+PgplbmRvYmoKMiAwIG9iago8PAovT3BlbkFjdGlvbiBbMyAwIFIgL0ZpdEggbnVsbF0KL1BhZ2VMYXlvdXQgL09uZUNvbHVtbgovUGFnZXMgMSAwIFIKL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDQgMCBSCi9QYXJlbnQgMSAwIFIKL1Jlc291cmNlcyA2IDAgUgovVHlwZSAvUGFnZQo+PgplbmRvYmoKNCAwIG9iago8PAovRmlsdGVyIC9GbGF0ZURlY29kZQovTGVuZ3RoIDIzNQo+PgpzdHJlYW0KeJxtjstOwzAURPf9ilmCFJk8KG67oyKVKCwC5Aec+DZxm/hGtkPJ31NaCQmV3Wg0OnNSbGexmEscZ+sSd5sESSriGOUOeflTZYlIFpDLuZASpcZNnuZ4Jz/2dIty/3f1IMV9el4VnQo7dj1y2xhL5HA0oUUxhZZthI3y4bF4jlCwD42jj7fXCE9cH8hFeBkrcpYCeXF9kS1FvLiIfA3kDNmaVliPpgs4EX0ErXxbsXL6lJXV0DR0PPVkAwYzUHfS+Q+cxEJmF3fHe6qDX2HLFbTxNX+Sm+CUPRjbnKFqDNyrYNj+or4BsGhiIQplbmRzdHJlYW0KZW5kb2JqCjUgMCBvYmoKPDwKL0Jhc2VGb250IC9IZWx2ZXRpY2EKL0VuY29kaW5nIC9XaW5BbnNpRW5jb2RpbmcKL1N1YnR5cGUgL1R5cGUxCi9UeXBlIC9Gb250Cj4+CmVuZG9iago2IDAgb2JqCjw8Ci9Gb250IDw8L0YxIDUgMCBSPj4KL1Byb2NTZXQgWy9QREYgL1RleHQgL0ltYWdlQiAvSW1hZ2VDIC9JbWFnZUldCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9DcmVhdGlvbkRhdGUgKEQ6MjAyNjA3MDYxMjA3MTJaKQo+PgplbmRvYmoKeHJlZgowIDgKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE1IDAwMDAwIG4gCjAwMDAwMDAxMDIgMDAwMDAgbiAKMDAwMDAwMDIwNSAwMDAwMCBuIAowMDAwMDAwMjg1IDAwMDAwIG4gCjAwMDAwMDA1OTIgMDAwMDAgbiAKMDAwMDAwMDY4OSAwMDAwMCBuIAowMDAwMDAwNzc2IDAwMDAwIG4gCnRyYWlsZXIKPDwKL1NpemUgOAovUm9vdCAyIDAgUgovSW5mbyA3IDAgUgovSUQgWzw1MUVENTA2NDFBRkNEMTQ2N0NGNzQzQzU0MTM5NTdCOT48NTFFRDUwNjQxQUZDRDE0NjdDRjc0M0M1NDEzOTU3Qjk+XQo+PgpzdGFydHhyZWYKODMxCiUlRU9GCg==",
  "base64",
);

test.describe("workspace workflows", () => {
  test("covers the main authenticated job-search loop", async ({ page }) => {
    test.setTimeout(120_000);
    await loginAsAdmin(page);

    const suffix = Date.now().toString(36);
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
    await expectOk(await page.request.patch(`/api/resumes/${resume.id}`, {
      data: { is_default: true, title: `E2E Resume ${suffix}` },
    }));

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
      source_url: "https://example.com/e2e-role",
      description: "Build Python, FastAPI, PostgreSQL, Docker, and Kubernetes services.",
      priority: "high",
    });
    const contact = await post<{ id: string }>(page, "/api/contacts", {
      job_id: job.id,
      name: `Taylor Recruiter ${suffix}`,
      company: `E2E Co ${suffix}`,
      role: "Recruiter",
      email: `taylor-${suffix}@example.com`,
      notes: "Met through E2E smoke test.",
      contacted: true,
    });
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
    await expect(page.getByText("Cover letters", { exact: true })).toBeVisible();
    await expect(page.getByText("Tailored resumes", { exact: true })).toBeVisible();
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
