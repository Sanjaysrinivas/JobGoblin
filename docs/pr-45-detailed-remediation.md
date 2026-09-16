# PR #45 Detailed Remediation And Merge-Readiness Plan

Status: **implemented** — correction series on `feature/post-merge-remediation`, 2026-09-16  
Prepared: 2026-09-16  
PR: `feature/post-merge-remediation` -> `dev`  
Reviewed head: `016f8cd01ca56705cf38aaee1c4a0ef58f556d60`  
Fixed baseline: `a961a254100a3d939e89af04777f0fef278bd410` (PR #44 merge)

## Resolution record

| Finding | Resolution |
| --- | --- |
| F1 technical token identity | `548fb43` — asymmetric technical-token boundaries; full section 4.5 matrix in `tests/test_grounding.py` |
| F2 immutable stored breakdowns | `4317bd1` — nullable snapshot columns (migration `b8c9d0e1f2a3`), stored breakdown serialization, `inputs_changed` |
| F3 legacy rerun resume | `9de3ab8` — `runAnalysis(resumeId)`; legacy button uses the analysis's resume, disabled when deleted. E2E covers the shared parameterized path; the legacy banner itself cannot be seeded through the API anymore (every new row stores a snapshot) |
| F4 failure-safe E2E | `fcf13e5` — Cleanup registry + finally teardown, `E2E_ALLOW_MUTATION` guard (CI sets it), profile save/restore, `scripts/e2e_artifact_report.py` dry-run report with exact-ID deletion |
| F5 presentation coverage | `ec62ac4` — N/A, 0/30, 0/5, normalization note asserted in-browser |
| F6 mobile + console gates | `ec62ac4` — Pixel 7 project (all specs, drawer-aware nav), console/page-error gate with one documented allowlist entry (pre-auth 401s), settings compared to `/api/runtime/configuration` and `/api/auth/me` |
| F7 stale remediation doc | `docs/post-merge-remediation.md` marked completed with per-item commits and verification summary |
| F8 applicability produced once | `4317bd1` — computed in `score_resume_for_job`, persisted from the single result; frontend fallback removed |
| F9 identity coordination | `af78fa2` — `find_duplicate_job`/`persist_job`/`JobIdentityConflict` in the service; threaded race test leaves exactly one job |
| F10 provider metadata | `8db686b` — `provider_name` moved to `ai_provider` |
| F11 hard-coded fallback | removed in `4317bd1`; results without a stored breakdown say so explicitly |

### Accepted deviations

- **Discovery cleanup (section 7.3)**: option 1 policy, not option 2 — no
  test-only backend endpoint was added. CI databases are ephemeral; local runs
  are explicit opt-ins via `E2E_ALLOW_MUTATION`, and the duplicate-save test
  cleans the saved job itself. Discovery runs/results rows persist only in
  opt-in local runs.
- **Legacy-banner E2E (section 6.4)**: rows without snapshots can no longer be
  created through the public API, so the banner's own click path is covered by
  the shared `runAnalysis(resumeId)` code path and type checks rather than a
  seeded legacy row.

## 1. Executive Summary

PR #45 successfully fixes most of the defects documented after PR #44. It builds,
passes its automated suite, runs in Docker, and improves the product materially.
However, it is still open on GitHub and should not be treated as merged or complete.

Three correctness problems remain merge blockers:

1. Source grounding still conflates distinct technical skills such as `C`, `C++`,
   `C#`, `NET`, and `.NET`.
2. Historical analyses are explained using the current mutable job description rather
   than the inputs and scoring rules that produced the stored score.
3. The legacy-analysis rerun action can analyze the default resume instead of the resume
   used by the selected legacy result.

The new E2E coverage is valuable, but several tests are not failure-safe and can leave
test jobs, resumes, applications, discovery runs, and discovery results in a persistent
workspace. This has already happened in the local admin workspace.

The recommended decision is: keep PR #45 open, add a focused correction series, rerun
all merge gates, then merge into `dev`.

## 2. Current Verification Evidence

The following passed at the reviewed head:

| Area | Result |
| --- | --- |
| Backend CI | Ruff and 321 pytest tests passed |
| Frontend CI | ESLint and Next.js 16.3.5 production build passed |
| Browser CI | 12 Docker/Caddy Playwright tests passed |
| Dependency audit | `npm audit --omit=dev` reported 0 vulnerabilities |
| Docker | Backend, frontend, PostgreSQL, and Caddy healthy |
| Database | Alembic at `a5b6c7d8e9f0`; no schema drift detected |
| API | Liveness and database readiness returned `200` |
| Manual browser | Desktop and 390 x 844 mobile views rendered |
| Browser errors | No application console errors during the smoke window |
| Resume transition | Deleting current and promoting replacement succeeded |
| Basic grounding | `Java`/`JavaScript`, `C`/`Cloud`, and `AI`/`chair` rejected |

These results establish that the branch is operational. They do not prove that every
domain rule is correct, because the remaining failures occur in cases not represented by
the current tests.

## 3. Severity And Merge Decision Matrix

| ID | Finding | Severity | Merge blocker | Primary owner area |
| --- | --- | --- | --- | --- |
| F1 | Technical skill tokens are conflated | Critical business correctness | Yes | Backend matching/grounding |
| F2 | Historical score breakdown uses mutable current job data | High trust/correctness | Yes | Analysis persistence/API |
| F3 | Legacy rerun may use the wrong resume | High user-data correctness | Yes | Analysis frontend |
| F4 | E2E cleanup is not retry/failure-safe | High test reliability/data hygiene | Yes | Playwright harness |
| F5 | Score applicability coverage is incomplete | Medium regression risk | Prefer before merge | Backend/frontend tests |
| F6 | Mobile and console gates are not encoded in Playwright | Medium regression risk | Prefer before merge | Playwright configuration |
| F7 | Remediation documentation still reports resolved work as open | Medium operational clarity | Yes | Documentation |
| F8 | Applicability logic is duplicated | Medium maintainability | No, if guarded by tests | Analysis service |
| F9 | Job identity coordination remains in route modules | Low/medium maintainability | No | Job/discovery services |
| F10 | Provider naming lives in the tailored-resume domain | Low maintainability | No | AI/observability service |
| F11 | Frontend retains obsolete hard-coded score fallback | Low/medium policy drift | Prefer before merge | Analysis frontend |

## 4. F1 - Preserve Exact Technical Skill Identity

### 4.1 Observed failure

The new boundary matching correctly prevents ordinary word substrings, but its boundary
definition only treats Unicode word characters as part of a token. Technical punctuation
such as `+`, `#`, and a leading `.` is considered a boundary, so shorter candidates match
inside longer, distinct technical skills.

Confirmed on the reviewed branch:

```python
is_source_supported("C", "Built C++ services")      # True; expected False
is_source_supported("C", "Built C# services")       # True; expected False
is_source_supported("NET", "Built .NET services")   # True; expected False
is_source_supported("C++", "Built C services")      # False; correct
```

Affected paths:

- `backend/app/services/grounding.py:is_source_supported`
- `backend/app/services/text_matching.py:contains_term`
- `backend/app/services/text_matching.py:contains_supported_term`
- Resume parsing through `ground_parsed_resume`
- Any discovery, analysis, or tailoring feature that consumes the shared matcher

### 4.2 Root cause

The matcher uses boundaries equivalent to:

```text
(?<!\w) TERM (?!\w)
```

For candidate `C`, the next character in `C++` is `+`, which is not a word character.
The regex therefore treats `C` as a complete match. The same problem occurs before
`NET` in `.NET` because `.` is not a word character.

### 4.3 Required domain decision

The matcher must distinguish exact technical identities while still supporting reviewed
aliases. Recommended canonical identities:

| Canonical skill | Allowed aliases | Must not imply |
| --- | --- | --- |
| `c` | `c` | `c++`, `c#` |
| `c++` | `c++`, `cpp` if explicitly approved | `c`, `c#` |
| `c#` | `c#`, `csharp` if explicitly approved | `c`, `c++` |
| `.net` | `.net`, `dotnet` if explicitly approved | generic `net` |
| `javascript` | `javascript`, `js` | `java` |
| `typescript` | `typescript`, `ts` | unrelated initials |

Do not infer language ancestry or ecosystem similarity as factual resume evidence.

### 4.4 Recommended implementation

1. Define the complete technical-token character set in one place. It should include
   characters that can participate in supported skill tokens, including `+`, `#`, `.`,
   and internal `-` where appropriate.
2. Make the start and end boundary checks aware of that character set.
3. Normalize aliases through `canonical_term`; do not solve the problem with special
   cases inside `grounding.py`.
4. Ensure alias matching compares complete variants, not prefixes of variants.
5. Retain current negation and aspirational-context filtering.

A possible implementation direction is a helper that compiles a term pattern using
technical-token boundaries rather than raw `\w` boundaries. The exact regex is less
important than the regression matrix below.

### 4.5 Required regression matrix

| Candidate | Source | Expected |
| --- | --- | --- |
| `C` | `Built services in C` | match |
| `c` | `Built services in C` | match |
| `C` | `Built services in C++` | reject |
| `C` | `Built services in C#` | reject |
| `C++` | `Built services in C++` | match |
| `C++` | `Built services in C` | reject |
| `C#` | `Built services in C#` | match |
| `C#` | `Built services in C++` | reject |
| `.NET` | `Developed .NET APIs` | match |
| `NET` | `Developed .NET APIs` | reject unless explicitly aliased |
| `Java` | `Developed JavaScript apps` | reject |
| `JavaScript` | `Developed JavaScript apps` | match |
| `Python` | `No Python experience` | reject |
| `Python` | `Learning Python` | reject |
| `Python` | `Five years of Python` | match |

Tests must cover both `contains_term` and `ground_parsed_resume` so a later change cannot
fix the utility while leaving the business pipeline broken.

### 4.6 Acceptance criteria

- A candidate skill is supported only by an exact canonical term or an approved alias.
- Technical punctuation cannot turn one skill into evidence for another.
- Negated and aspirational mentions remain unsupported.
- All analysis, discovery, tailoring, and parser tests continue to pass.

## 5. F2 - Make Stored Analysis Explanations Immutable And Reproducible

### 5.1 Observed failure

`analysis_response` calls `applicable_categories` using the job's current title and
description every time a stored analysis is returned. The numeric category scores and
overall score were produced earlier, potentially from different job text and a different
scoring model.

Consequences:

- Editing a job can change which categories an old analysis marks applicable.
- The same stored analysis can display a different breakdown on different days.
- Legacy results created with formatting weight are displayed using the new model that
  excludes formatting.
- The displayed earned/max totals may not mathematically reconcile to the stored overall
  percentage.

This was visible in the live app: a legacy analysis stored as 84% displayed current-model
category values and an `N/A` education category that could not reproduce 84%.

Affected paths:

- `backend/app/api/routes/analysis.py:analysis_response`
- `backend/app/services/job_analysis.py:applicable_categories`
- `backend/app/models/core.py:JobAnalysis`
- `backend/app/schemas/analysis.py:JobAnalysisOut`
- `frontend/components/jobs/job-analysis-panel.tsx`

### 5.2 Required persistence model

New analyses should persist the explanation inputs needed to reproduce their score. At
minimum, store:

```text
analysis_version        stable scoring/matcher version
score_breakdown         JSON array of key, label, earned, maximum, applicable
job_text_hash           hash of normalized title + description used at analysis time
resume_version_id       exact resume version used, when available
resume_text_hash        hash of normalized resume evidence used at analysis time
```

Recommended future-compatible fields:

```text
requirements_snapshot   extracted required/preferred/negated requirements with provenance
matcher_version         separate version if matching evolves independently of scoring
```

Hashes are for change detection and auditability, not for reconstructing deleted text.
The score breakdown itself must be persisted because it is the human explanation of the
stored score.

### 5.3 API behavior

For a new grounded analysis:

- Return the persisted `score_breakdown` exactly as calculated at creation.
- Return `is_legacy=false`.
- Return input-change indicators when current job/resume hashes differ from stored hashes.
- Offer rerun rather than silently recomputing the explanation.

For an existing legacy analysis:

- Return `is_legacy=true`.
- Do not fabricate a new-model breakdown from current job text.
- Either return `score_breakdown=null` with a clear explanation, or render a versioned
  legacy breakdown only if the original model's weights are known with certainty.
- Preserve the stored numeric result and recommendations as historical data.

### 5.4 Migration strategy

1. Add nullable columns for the new metadata. Existing rows remain valid legacy rows.
2. Do not backfill historical breakdowns from current job/resume state.
3. Stamp every newly created analysis with the current versions and hashes.
4. Treat rows missing the required snapshot metadata as legacy even if a string field
   happens to equal the current version name.
5. Provide a downgrade that removes only the new metadata columns; do not delete analyses.

### 5.5 Regression coverage

- Create an analysis, edit the job description, retrieve the analysis, and assert its
  persisted breakdown is unchanged.
- Create an analysis, edit the resume, retrieve the analysis, and assert the breakdown is
  unchanged and the response reports stale inputs.
- Assert the category totals reproduce the stored overall score within the documented
  rounding rule.
- Assert legacy rows do not receive a fabricated current-model breakdown.
- Test jobs with no education requirement (`N/A`) and jobs with a required education
  category but no resume evidence (`0/5`).
- Test a required skills category with no matching evidence (`0/30`).

### 5.6 Acceptance criteria

- A stored result has one stable explanation for its lifetime.
- Editing a job or resume never rewrites history at response time.
- Every non-legacy overall score can be reproduced from its persisted breakdown.
- Legacy results are visibly historical and never presented as current grounded output.

## 6. F3 - Rerun A Legacy Analysis With Its Original Resume

### 6.1 Observed failure

The analysis panel initializes `selectedResumeId` from the default or first resume.
Selecting a historical analysis does not synchronize that state with
`selectedAnalysis.resume_id`. Both the main “Run analysis” button and the legacy
“Run updated analysis” button call the same parameterless `runAnalysis` function.

If the legacy analysis belongs to resume B while resume A is the default, clicking
“Run updated analysis” creates a new analysis for resume A.

The live UI reproduced this mismatch: the resume selector showed the default E2E resume
while the selected legacy analysis was labelled with a different resume.

Affected path:

- `frontend/components/jobs/job-analysis-panel.tsx`

### 6.2 Required interaction contract

- The ordinary “Run analysis” action uses the explicitly selected resume.
- The legacy “Run updated analysis” action uses the selected analysis's `resume_id`.
- Changing the historical-analysis selector should not silently change the main resume
  selector unless the UI clearly communicates that coupling.
- If the historical resume has been deleted, disable rerun and explain why.

### 6.3 Recommended implementation

Change the action to accept an explicit resume ID:

```typescript
async function runAnalysis(resumeId: string) {
  // validate resumeId and submit it
}
```

Then wire:

```text
Run analysis          -> runAnalysis(selectedResumeId)
Run updated analysis  -> runAnalysis(selectedAnalysis.resume_id)
```

After a successful legacy rerun, select the newly created analysis and optionally align
the resume selector with the used resume so the screen state remains understandable.

### 6.4 Required tests

1. Create resume A as default.
2. Create resume B.
3. Create/select a legacy analysis belonging to resume B.
4. Confirm the main selector still shows resume A.
5. Click “Run updated analysis”.
6. Assert the request payload contains resume B's ID.
7. Assert the resulting analysis label identifies resume B.
8. Repeat with resume B deleted and assert rerun is disabled with an explanation.

### 6.5 Acceptance criteria

- The rerun action can never silently switch the candidate resume.
- The user can see which resume will be analyzed before confirming the operation.

## 7. F4 - Make E2E Tests Failure-Safe And Workspace-Safe

### 7.1 Observed failure

Only the first two new remediation tests use `try/finally`. Later tests perform cleanup
after assertions. Any failed assertion, browser failure, timeout, or retry skips those
cleanup statements. Discovery runs and results have no cleanup at all.

The local admin workspace currently contains test-named jobs, resumes, applications, and
reminders from earlier E2E activity. Besides polluting user data, this can make retries
pass or fail for the wrong reason.

Affected paths:

- `frontend/e2e/remediation.spec.ts`
- `frontend/e2e/workspace.spec.ts`
- `frontend/playwright.config.ts`

### 7.2 Required cleanup architecture

Use a cleanup registry per test:

```text
applications -> outreach/prep/cover letters -> resumes -> jobs -> discovery data
```

Every resource ID must be registered immediately after creation. Run cleanup from a
`finally` block or fixture teardown in reverse dependency order. Cleanup should be
idempotent and tolerate `404`.

Do not depend on the final test line being reached.

### 7.3 Discovery cleanup decision

Discovery runs/results currently lack a normal delete workflow. Choose one explicit
testing strategy:

1. Preferred: run E2E only against an ephemeral database that is destroyed after the
   suite, and refuse mutation of a non-test environment.
2. Acceptable: provide a test-only cleanup fixture or command enabled exclusively when
   `APP_ENV=test`; it must not be exposed in production.
3. Avoid: adding a production bulk-delete endpoint solely for test convenience.

Add an environment guard such as `E2E_ALLOW_MUTATION=true` so a developer cannot
accidentally run the destructive suite against their personal workspace.

### 7.4 Existing local artifacts

Do not broadly delete data by title prefix without review. Provide a dry-run cleanup
report for known test patterns such as:

```text
E2E Resume ...
E2E Co ...
Platform Engineer mu...
Remediation Engineer ...
Remediation Co ...
https://example.com/e2e-role-...
https://example.com/remediation-...
```

Deletion should require explicit operator confirmation and target exact IDs discovered
by the dry run. Preserve any similarly named real user record.

### 7.5 Retry-safety tests

- Force a failure after resource creation and verify teardown removes the resources.
- Run the same test twice and verify the second run is independent.
- Run with CI retries enabled and confirm duplicate protection does not create false
  failures.
- Confirm the suite refuses to mutate a non-test environment without the explicit guard.

### 7.6 Acceptance criteria

- No test resource remains after a pass, failure, timeout, or retry.
- Discovery tests do not permanently add runs/results to a personal workspace.
- Test success never depends on state left by a previous attempt.

## 8. F5/F6 - Complete Browser And Presentation Regression Coverage

### 8.1 Score presentation coverage

Add frontend assertions for:

- Non-applicable education renders `N/A`.
- Applicable education with zero evidence renders `0/5`.
- Category progress/tone uses `earned / maximum`, not raw earned points.
- Overall explanatory text says only applicable categories are counted.
- Legacy results do not render an invented new-model breakdown.

Prefer component tests if a frontend unit-test framework is introduced; otherwise keep
one focused browser scenario with deterministic API data.

### 8.2 Mobile project

Add a mobile Playwright project, for example a supported phone device or an explicit
`390 x 844` viewport. At minimum cover:

- Application list and material selectors.
- Job detail analysis panel.
- Navigation drawer.
- Settings provider cards.
- Dashboard metrics.

Tests must not merely confirm the page loaded. Assert that primary controls are visible,
reachable, and not horizontally clipped.

### 8.3 Console and page-error gate

Create a shared fixture that records:

```text
page.on("console") for error-level messages
page.on("pageerror") for uncaught exceptions
failed API responses where appropriate
```

Fail the test during teardown if unexpected errors occurred. Maintain a narrow allowlist
only for understood third-party/browser warnings, with an explanatory comment.

### 8.4 Settings truthfulness test

The current settings test checks for labels. Strengthen it by fetching
`/api/runtime/configuration` and `/api/auth/me`, then asserting the exact returned values
appear in the UI. This proves the screen is live rather than a convincing placeholder.

## 9. F7 - Close Or Archive The Remediation Documentation

The existing `docs/post-merge-remediation.md` is linked as essential documentation but
still says all work is open. Once the blocking items in this document are complete:

1. Change its status to completed and record the merge commit/date.
2. Mark each numbered item completed with the implementing commit or PR reference.
3. Move any intentionally deferred item into `docs/roadmap.md` rather than leaving it
   ambiguously open.
4. Add a verification section containing final CI counts, migration checks, dependency
   audit result, and browser matrix.
5. Make this document historical or update its status so it does not become another
   stale source of truth.

Documentation is part of the Definition of Done, not an after-merge cleanup task.

## 10. F8 - Produce Applicability Once

Scoring and response presentation currently reconstruct category applicability in two
places. A future category-rule change can update one and not the other.

Recommended design:

```text
score_resume_for_job
  -> DeterministicScores
       - earned category scores
       - applicable categories
       - applicable total weight
       - normalized overall
       - matched/missing evidence
```

Persist the generated breakdown from this single result. `analysis_response` should
serialize stored facts, not recalculate scoring policy.

Remove frontend hard-coded fallback weights once the API contract is required. If mixed
frontend/backend versions must be supported, version the API explicitly rather than
silently inventing fallback policy.

## 11. F9 - Finish Job Identity Coordination Behind A Service

Tailored-resume orchestration was successfully moved out of `jobs.py`. Job identity
coordination remains spread across job creation/update and discovery save flows.

Create a focused service responsible for:

- Computing the canonical identity key.
- Finding an existing user-owned job.
- Creating a job atomically.
- Updating identity-bearing fields safely.
- Translating uniqueness races into a domain result.
- Reusing the saved job from discovery.

Routes should remain responsible for authentication, request validation, ownership, HTTP
status mapping, and response serialization. They should not independently reimplement the
identity transaction.

Required concurrency test: two transactions attempt to save the same user/job identity;
the result is one job and deterministic reuse/conflict behavior, not a `500`.

## 12. F10 - Move Provider Identity To The AI/Observability Layer

Generic provider-name extraction is currently imported from the tailored-resume service
by the jobs route. Move it to `ai_provider.py` or a small observability helper so job
import telemetry does not depend on the tailored-resume domain.

Acceptance criteria:

- Tailored resume code consumes the shared provider metadata helper.
- Job import consumes the same helper.
- Neither domain imports utility behavior from the other.

## 13. Recommended Commit Series

Keep corrections reviewable and bisectable:

1. `fix(grounding): preserve technical token identity`
2. `fix(analysis): persist reproducible score breakdowns`
3. `fix(frontend): rerun legacy analysis with source resume`
4. `test(e2e): make resource cleanup failure-safe`
5. `test(e2e): add mobile and console error gates`
6. `refactor(jobs): centralize identity transactions`
7. `refactor(ai): centralize provider metadata`
8. `docs: close post-merge remediation plan`

Do not combine the analysis persistence migration with unrelated route refactors.

## 14. Required Validation Sequence

### 14.1 Static and unit verification

```powershell
Set-Location backend
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m pytest -q

Set-Location ..\frontend
npm run lint
npm run build
npm audit --omit=dev
```

### 14.2 Migration verification

Against an isolated PostgreSQL database:

1. Upgrade from the PR #44 schema to the new head.
2. Confirm existing analyses remain present and are classified legacy.
3. Create a new analysis and inspect stored version/breakdown/hash metadata.
4. Downgrade one revision.
5. Re-upgrade to head.
6. Run `alembic check`.

### 14.3 Docker verification

```powershell
docker compose up -d --build
docker compose ps
Invoke-WebRequest -UseBasicParsing http://localhost:8080/api/health
Invoke-WebRequest -UseBasicParsing http://localhost:8080/api/health/ready
docker compose exec -T backend alembic current
docker compose exec -T backend alembic check
```

If the local environment enables the optional Cloudflare profile, stop it after testing
unless external sharing is intentionally required:

```powershell
docker compose stop cloudflared
```

### 14.4 Browser verification

Run both desktop and mobile projects through the Caddy origin. Confirm:

- Login and MFA skip/challenge paths.
- Legacy analysis warning and correct-resume rerun.
- Stable historical score breakdown after editing current job data.
- New analysis category `N/A` and required-but-zero states.
- Resume-version deletion and replacement display.
- Application material compatibility.
- Track/View Tracker transition.
- Cumulative applied count.
- Settings exact runtime/account values.
- Zero unexpected console errors and page exceptions.

### 14.5 Data hygiene verification

After successful, failed, and retried E2E runs:

- Query for the generated unique suffixes.
- Confirm no test jobs, resumes, applications, cover letters, discovery runs, or results
  remain.
- Confirm real user records were not modified.

## 15. Final Merge Checklist

PR #45 is ready to merge only when every required item is checked:

- [ ] `C`, `C++`, `C#`, `NET`, and `.NET` grounding tests pass with correct identity.
- [ ] Grounded resume parsing uses the corrected shared matcher.
- [ ] New analyses persist versioned, immutable score breakdown metadata.
- [ ] Legacy analyses do not receive a fabricated current-model breakdown.
- [ ] Editing current job/resume content cannot change a historical explanation.
- [ ] Legacy rerun always uses `selectedAnalysis.resume_id`.
- [ ] Deleted source resumes disable rerun with a clear message.
- [ ] Required-but-zero and non-applicable categories have backend and UI coverage.
- [ ] Every mutating E2E test cleans up in fixture teardown or `finally`.
- [ ] Discovery E2E data is ephemeral or removed by test-only teardown.
- [ ] The suite refuses unsafe mutation of a personal/non-test workspace.
- [ ] Desktop and mobile Playwright projects pass.
- [ ] Unexpected console errors and page exceptions fail tests.
- [ ] Settings values are compared with actual API responses.
- [ ] Existing local test artifacts have a reviewed, ID-specific cleanup plan.
- [ ] Remediation documentation reflects final shipped status.
- [ ] Backend full suite and Ruff pass.
- [ ] Frontend lint, build, and production dependency audit pass.
- [ ] Migration upgrade/downgrade/re-upgrade and drift checks pass.
- [ ] Fresh Docker Compose build and health checks pass.
- [ ] PR is actually merged and `origin/dev` contains its merge commit.

## 16. Explicit Non-Goals

This correction should not expand into:

- A large custom skills ontology.
- Semantic embeddings or vector search.
- Silent rewriting of historical analyses.
- Destructive cleanup of user data based only on title prefixes.
- A production-only endpoint created solely for E2E teardown.
- Automatic outreach, email sending, or job application submission.

The goal is narrow: make the existing grounded, review-first workflow truthful,
reproducible, test-safe, and ready to merge.

