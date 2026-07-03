# JobGoblin Roadmap

This roadmap describes where JobGoblin is now, what the final application should become, and the remaining work needed to get there. It intentionally avoids dates and timelines.

## Product Direction

JobGoblin is a private, self-hosted job-search workspace for one owner and a small set of invited users. It should help users discover relevant job opportunities, organize saved roles, understand resume fit, draft application materials, plan follow-ups, and prepare for interviews while keeping every external action under human control.

The first Job Discovery slice is implemented: users can define preferences, search through the configured provider, review deduped discovered roles, get AI-assisted ranking, and explicitly save good matches into the normal jobs workflow. The next discovery work is hardening provider coverage, ranking explanations, and operations around real local LLM behavior.

The product boundaries are fixed:

- JobGoblin is not an auto-apply tool.
- JobGoblin does not silently send email, contact recruiters, submit forms, scrape LinkedIn, or perform external outreach.
- Job discovery stops at finding, ranking, and saving candidate roles; applying and outreach remain manual user actions.
- AI output must stay grounded in user-provided facts: resumes, profiles, job descriptions, notes, contacts, and application history.
- User data must remain scoped by `user_id`.
- The default deployment remains private and self-hosted.

## Where We Are Now

The application has moved past the foundation stage and now has most of the MVP workflow in place.

Implemented:

- Local Docker Compose stack with PostgreSQL, FastAPI backend, Next.js frontend, Caddy, optional Ollama, and optional Cloudflare Tunnel.
- Invite-only authentication with email/password, admin invite tokens, allowlist support, Google OAuth plumbing, TOTP MFA, and environment-aware cookies.
- Resume upload, text extraction, AI parsing, editing, listing, detail view, deletion, and PDF export.
- Resume versions from PR #25, including duplicate/version flows, current-version handling, source-fact preservation, version detail UI, and version export behavior.
- Job CRUD with list, create, detail, edit, delete, and source metadata.
- Contacts CRUD for recruiters, referrals, and job-linked relationships.
- Applications workflow with status tracking, notes, activity events, and follow-up reminders.
- Dashboard with pipeline counts, follow-up counts, average analysis score, and recent activity.
- Resume-to-job analysis with deterministic scoring, AI explanation, persisted results, and estimate language in the UI.
- Cover-letter draft generation, editing, statuses, and job-detail UI.
- Review-only outreach draft workflow with local copy/export behavior.
- Profile builder seeded from parsed resume sections and editable by the user.
- Job Discovery MVP from PR #28, including preferences, mock/Adzuna provider plumbing, run/result storage, dedupe, review/dismiss/save states, `/discover` UI, and save-to-job behavior.
- AI-assisted discovery ranking from PR #29 using preferences, profile, resumes, and saved job context with deterministic fallback behavior.
- Playwright E2E harness through Docker Compose and Caddy.
- Runtime operator tooling for Ollama checks, runtime smoke tests, and Cloudflare Tunnel checks.
- Real local Ollama runtime with `llama3.2:3b` proven through Caddy smoke coverage for resume parsing, resume-to-job analysis, and cover-letter generation.

Still needs verification:

- Full integrated verification after the latest merged feature set.
- Google OAuth with real credentials and allowlisted users.
- Cloudflare Tunnel HTTPS access and secure-cookie behavior.
- End-to-end manual UX pass across the full job-search loop.

## Final Application State

The final JobGoblin application should feel like a private command center for a job search.

A user should be able to:

- Sign in securely through local or tunnel access.
- Maintain a trusted master profile of their own facts.
- Upload multiple resumes and manage resume versions.
- Define job preferences, countries, and locations for discovery.
- Review discovered jobs from web/search providers.
- See local-AI ranking and fit reasoning before saving a discovered role.
- Save jobs and keep the original posting text.
- Compare any resume or tailored draft against any saved job.
- See clear estimated match scores, matched keywords, gaps, and recommendations.
- Generate grounded cover-letter drafts from selected resume/profile/job facts.
- Generate tailored resume drafts without inventing experience or credentials.
- Track contacts, recruiters, referrals, outreach drafts, and conversation notes.
- Track each application from saved role through interviews, offer, rejection, withdrawal, or archival.
- See upcoming follow-ups and recent activity without relying on memory.
- Prepare for interviews from the job description, resume/profile, and application notes.
- Export or copy drafts for manual use.
- Keep every external action explicit and human-reviewed.

The app should not need any hosted SaaS backend to function. The normal operating model should be local-first, with optional private tunnel access.

## Remaining Roadmap

### 1. Stabilize The Merged MVP

Goal: make the merged feature set reliable enough to use daily.

Remaining work:

- Keep local `dev` aligned with the latest merged state.
- Validate merged resume-version workflows.
- Validate merged job discovery and AI ranking workflows.
- Run backend ruff and pytest.
- Run frontend lint and build.
- Run Playwright E2E through Docker Compose and Caddy.
- Start the full local stack and manually smoke the main flows:
  - login and MFA
  - resumes
  - jobs
  - analysis
  - contacts
  - applications
  - follow-up reminders
  - dashboard
  - cover letters
  - outreach drafts
  - profile builder
  - resume versions
  - job discovery and AI ranking
- Fix regressions found during the integrated pass.
- Keep README, architecture, design, frontend notes, and handover docs aligned with the merged code.

Done when:

- The app works through `http://localhost:8080`.
- CI and local verification agree.
- Docs do not describe merged features as planned or placeholders.

### 2. Harden The Real Local AI Runtime

Goal: keep proven local model behavior useful and reliable.

Remaining work:

- Keep `llama3.2:3b` documented as the proven local baseline.
- Manually inspect AI output quality for grounding and usefulness.
- Tune prompts or parsing behavior where outputs are weak.
- Document the working local AI setup.

Done when:

- Browser workflows produce useful real AI output.
- The app still works without external AI APIs.
- AI output remains grounded in user-provided facts.

### 3. Add LLM Observability

Goal: make local LLM behavior diagnosable without leaking resume, profile, prompt, or credential data.

Remaining work:

- Capture provider, model, operation name, latency, success/failure, timeout, and fallback use for parsing, analysis, cover letters, and discovery ranking.
- Redact prompts, resume text, profile facts, secrets, tokens, and raw job descriptions from logs.
- Surface operator diagnostics for unavailable models, malformed JSON, slow responses, and deterministic fallback paths.
- Document retention and privacy boundaries for any LLM telemetry.

Done when:

- The owner can tell whether an AI issue is model availability, slow runtime, malformed output, prompt quality, or fallback behavior.
- Observability does not expose sensitive user-provided facts.

### 4. Prove Private External Access

Goal: make the app usable from a private HTTPS URL without weakening security.

Remaining work:

- Configure Cloudflare Tunnel for the local Caddy origin.
- Configure Google OAuth redirect settings for the tunnel hostname.
- Verify owner login through the tunnel.
- Verify allowlisted friend login through the tunnel.
- Verify unallowlisted users are rejected.
- Confirm production-mode cookies are `Secure`, `HttpOnly`, and `SameSite=Lax`.
- Document operator steps and failure modes.

Done when:

- The owner and invited users can access the app through HTTPS.
- The app remains private and allowlist-gated.
- Local-only operation still works without tunnel credentials.

### 5. Harden Job Discovery

Goal: make the merged discovery and ranking flow reliable enough for daily use.

Implemented:

- User job preferences for role titles, work mode, countries, locations, keywords, exclusions, visa sponsorship, and blocked companies.
- Mock provider for local/dev and Adzuna provider plumbing behind configuration.
- Separate discovered result storage, run records, dedupe, review/dismiss/save states, and save-to-job behavior.
- `/discover` UI for running searches and saving selected results.
- AI-assisted ranking using preferences, profile, resumes, and saved job history, with deterministic fallback behavior.

Remaining work:

- Add richer provider coverage beyond the first provider.
- Smoke test Adzuna credentials and real local Ollama ranking through the browser flow.
- Improve ranking explanations for location, visa, and work-mode compatibility.
- Keep discovery read-only toward the outside world: no auto-apply, no silent outreach, and no background contact.

Done when:

- A user can run discovery for chosen countries and locations.
- Discovered results are stored, deduped, ranked, and reviewable.
- A user can save a discovered role as a normal job.
- Discovery never performs external application or outreach actions.

### 6. Add Tailored Resume Drafts

Goal: generate reviewable resume drafts for a specific job using only verified user facts.

Remaining work:

- Use profile, selected resume/version, job description, and analysis gaps as inputs.
- Generate tailored bullet suggestions and section edits.
- Show what changed and why.
- Block invented companies, credentials, dates, or skills.
- Let the user accept, edit, reject, or export draft changes.
- Persist tailored drafts with status and provenance.

Done when:

- A user can create a tailored resume draft for a job.
- Every generated change is editable and grounded.
- The app clearly distinguishes source facts from AI-suggested wording.

### 7. Improve Application Workflow Links

Goal: connect jobs, resumes, cover letters, outreach, contacts, and follow-ups into one coherent workflow.

Remaining work:

- Link applications to selected resume versions and cover-letter drafts.
- Show related contacts and outreach drafts from the application view.
- Make next action and follow-up state more visible.
- Add richer activity events for meaningful workflow changes.
- Add filters for active, due, interviewing, archived, and outcome states.

Done when:

- The application detail view explains the full state of a job pursuit.
- Users can quickly answer what happened, what was sent manually, and what comes next.

### 8. Add Email Draft And Export Integration

Goal: make outbound communication easier while preserving explicit human review.

Remaining work:

- Generate email-style drafts for recruiter follow-ups, referrals, thank-yous, and status checks.
- Support copy/export actions and record them locally.
- Optionally open a mail client with a draft only after explicit user action.
- Avoid background sending.
- Keep a clear audit trail of copied/exported drafts.

Done when:

- JobGoblin helps prepare messages but never sends them silently.
- Users can track what they manually used outside the app.

### 9. Add Interview Prep

Goal: turn saved jobs and user facts into practical interview preparation.

Remaining work:

- Generate likely interview questions from the job description.
- Generate user-grounded answer outlines from resume/profile facts.
- Add STAR/story bank support.
- Add company/job-specific preparation notes.
- Track interview rounds and prep status on applications.

Done when:

- Users can prepare for interviews from the same trusted data already in JobGoblin.
- AI answers remain suggestions, not fabricated claims.

### 10. Harden Operations And Maintenance

Goal: make the private deployment boring to run.

Remaining work:

- Add backup and restore guidance for Postgres volumes and uploaded files.
- Add migration and rollback guidance.
- Add health checks and operator diagnostics.
- Include LLM observability in routine operator checks once the telemetry track lands.
- Improve startup failure messages.
- Document secrets handling.
- Decide whether `main` should receive stable releases from `dev`.

Done when:

- The owner can recover data, update the app, and diagnose common failures without digging through code.

## Definition Of Done For The Final Product

JobGoblin reaches its final intended state when:

- The core job-search loop is complete from resume/profile to preference-based job discovery, saved matches, analysis, tailored drafts, application tracking, follow-up, outreach prep, and interview prep.
- Real local AI works reliably through Ollama.
- The app is usable through local Caddy and optional HTTPS tunnel access.
- User isolation and invite-only access are enforced.
- External actions remain explicit and human-reviewed.
- Generated content is grounded, editable, and traceable to user-provided facts.
- The owner has clear docs for setup, operation, backup, restore, and troubleshooting.
