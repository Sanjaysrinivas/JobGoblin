# JobGoblin Roadmap

This roadmap describes where JobGoblin is now, what the final application should become, and the remaining work needed to get there. It intentionally avoids dates and timelines.

## Product Direction

JobGoblin is a private, self-hosted job-search workspace for one owner and a small set of invited users. It should help users discover relevant job opportunities, organize saved roles, understand resume fit, draft application materials, plan follow-ups, and prepare for interviews while keeping every external action under human control.

Job Discovery is implemented: users can define preferences, search through the configured provider, review deduped discovered roles, get AI-assisted ranking with deterministic fallback, and explicitly save good matches into the normal jobs workflow. Discovery remains read-only toward the outside world.

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
- Review-only outreach draft workflow with local copy/export behavior and explicit email export/copy/mail-client handoff.
- Profile builder seeded from parsed resume sections and editable by the user.
- Tailored resume-version drafts for saved jobs, with source version provenance and PDF export through the resume-version export path.
- Interview prep packets for saved jobs/applications using job, resume, and resume-version context, with editable notes/status.
- Sanitized LLM observability hooks for provider/model/operation, prompt/schema hashes, latency, success/failure, and deterministic fallback visibility.
- Job Discovery MVP from PR #28, including preferences, mock/Adzuna provider plumbing, run/result storage, dedupe, review/dismiss/save states, `/discover` UI, and save-to-job behavior.
- AI-assisted discovery ranking from PR #29 using preferences, profile, resumes, and saved job context with deterministic fallback behavior.
- Playwright E2E harness through Docker Compose and Caddy.
- Runtime operator tooling for Ollama checks, DB readiness, runtime smoke tests, Cloudflare Tunnel checks, and operator guidance for Adzuna, OAuth, backups, restores, migrations, rollback, secrets, and release promotion.
- Real local Ollama runtime with `llama3.2:3b` proven through Caddy smoke coverage for resume parsing, resume-to-job analysis, and cover-letter generation.

Still needs verification:

- Full integrated verification after the latest merged feature set.
- Adzuna discovery with real credentials and supported country/location choices.
- Real local Ollama behavior through the browser for ranking and generated drafts/prep.
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

### 1. Integrated Release Validation

Goal: prove the merged MVP works as one private workflow, not just as isolated slices.

Validation gates:

- Run backend ruff and pytest with the test PostgreSQL database available on `localhost:5433`.
- Run frontend lint and build.
- Run Playwright E2E through Docker Compose and Caddy.
- Start the full local stack and manually smoke the main flows: login/MFA, resumes and resume versions, jobs, discovery and AI ranking, analysis, tailored drafts, cover letters, outreach export, interview prep, contacts, applications, follow-ups, dashboard, and profile builder.
- Fix regressions found during that integrated pass.

Done when:

- The app works through `http://localhost:8080`.
- CI and local verification agree.
- Docs do not describe merged features as planned or placeholders.

### 2. Real Runtime Validation

Goal: keep local model behavior useful and diagnosable without external AI APIs.

Validation gates:

- Keep `llama3.2:3b` documented as the proven local baseline.
- Manually inspect real Ollama output quality for grounding and usefulness across parsing, analysis, cover letters, tailored drafts, discovery ranking, and interview prep.
- Verify sanitized observability spans/events when `OBSERVABILITY_ENABLED=true`: provider, model, operation, latency, success/failure, and fallback reason without prompt, resume, profile, job text, tokens, or secrets.
- Tune prompts or parsing behavior only where the real browser workflow shows weak output.

Done when:

- Browser workflows produce useful real AI output.
- The app still works without external AI APIs.
- AI diagnostics identify slow runtime, malformed output, unavailable models, and fallback paths without exposing sensitive user text.

### 3. Operator-Run External Validation

Goal: validate integrations that require private credentials without pretending tests can prove them.

Validation gates:

- Adzuna: set `JOB_DISCOVERY_PROVIDER=adzuna`, `ADZUNA_APP_ID`, and `ADZUNA_APP_KEY`; run discovery for supported countries/locations; confirm failed runs never log API keys or provider URLs with secrets.
- Google OAuth: set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_BASE_URL`, and `ALLOWED_EMAILS`; verify owner login, allowlisted friend login, and unallowlisted rejection.
- Cloudflare Tunnel: set `CLOUDFLARED_TUNNEL_TOKEN`; verify HTTPS access to Caddy, Google redirect URI alignment, and production cookies as `Secure`, `HttpOnly`, and `SameSite=Lax`.

Done when:

- The owner and invited users can access the app through HTTPS when the tunnel profile is enabled.
- The app remains private and allowlist-gated.
- Local-only operation still works without tunnel, OAuth, or Adzuna credentials.

### 4. Discovery Operations Hardening

Goal: make discovery reliable enough for daily use while keeping it read-only externally.

Implemented:

- User preferences for role titles, work mode, countries, locations, keywords, exclusions, visa sponsorship, and blocked companies.
- Mock provider for local/dev and Adzuna provider plumbing behind configuration.
- Country/provider validation, sanitized provider failure messages, run/result storage, dedupe, review/dismiss/save states, and save-to-job behavior.
- AI-assisted ranking using preferences, profile, resumes, and saved job history, with deterministic fallback telemetry.
- Ranking explanations for keyword/profile matches, title, location, work mode, and visa-sponsorship visibility.

Remaining work:

- Do not add another discovery provider until there is real code/config that makes it cheap to operate.
- Use Adzuna credential smoke results to decide whether provider coverage is actually insufficient.
- Keep discovery read-only: no auto-apply, no silent outreach, and no background contact.

Done when:

- A user can run discovery for chosen countries and locations.
- Discovered results are stored, deduped, ranked, and reviewable.
- A user can save a discovered role as a normal job.
- Discovery never performs external application or outreach actions.

### 5. Operations And Maintenance

Goal: make the private deployment boring to run.

Remaining work:

- Keep backup and restore guidance current for Postgres volumes and uploaded files.
- Keep migration, rollback, secrets, and release-promotion guidance current.
- Include LLM observability and provider diagnostics in routine operator checks.
- Improve startup failure messages when real operator runs expose unclear failures.
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
