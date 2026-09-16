# Post-Merge Remediation Plan

Status: **completed** — delivered on `feature/post-merge-remediation` (PR #45), 2026-09-16
Last verified: 2026-09-16
Baseline: `dev` at merge commit `a961a254100a3d939e89af04777f0fef278bd410`

## Completion record

| Item | Implementing commit |
| --- | --- |
| 1. Boundary-aware grounding | `ef74918`, hardened by `548fb43` |
| 2. Current-version deletion fix | `66e96b9` |
| 3. Dependency upgrades (audit clean) | `147dc50` |
| 4. Score applicability + N/A UI | `cca0c05`, superseded by `4317bd1` (persisted breakdowns) |
| 5. Legacy analysis labeling/rerun | `eaba80f`, `4317bd1`, `9de3ab8` |
| 6. E2E coverage | `4c228bf`, `fcf13e5`, `ec62ac4` |
| 7. Docs synchronized | `b421358`, `016f8cd` |
| 8. Migration/runtime equivalence | `c69303a` |
| 9. Synchronous deterministic analysis | `c791685` |
| 10. Shared material selection | `d6ffb8b` |
| 11. Jobs route thinning | `d6ffb8b`, `af78fa2` |
| 12. GHCR policy confirmed (keep) | `016f8cd` (runbook section 16) |

Final verification on the branch head: 343 backend tests + Ruff, frontend
tsc/ESLint/build + `npm audit --omit=dev` clean, 26 Playwright tests
(13 specs × desktop + Pixel 7 mobile) with console-error gates, Alembic
upgrade/downgrade/re-upgrade + drift checks, fresh Docker Compose build
with all services healthy. Follow-up findings from the detailed review
are tracked in [pr-45-detailed-remediation.md](pr-45-detailed-remediation.md).

## Purpose

PR #44 delivered the agreed grounding, scoring, application-workflow, data-integrity,
authentication, and UI-honesty changes. The merged application builds and its normal
browser workflow works, but post-merge verification found correctness, presentation,
test-coverage, documentation, and dependency issues that should be resolved before the
remediation is considered complete.

This document is the implementation checklist for that follow-up work. It intentionally
separates product defects from maintainability improvements.

## Verification Baseline

The following passed on the merged commit:

- GitHub Actions: backend Ruff and 292 pytest tests.
- GitHub Actions: frontend lint and production build.
- GitHub Actions: five Docker-backed Playwright tests.
- Fresh local frontend and backend container builds.
- Docker health checks for PostgreSQL, backend, frontend, and Caddy.
- `GET /api/health` and `GET /api/health/ready`.
- Alembic migration head and `alembic check` with no detected schema drift.
- Desktop and 390 px mobile browser smoke tests with no console errors.

Passing checks do not cover the defects below.

## P0 — Correctness And Security

### 1. Make AI source grounding boundary-aware

**Problem**

`backend/app/services/grounding.py:is_source_supported` normalizes the candidate and
source, then uses unrestricted substring matching. This permits unsupported facts when
one term is contained inside another word.

Confirmed examples:

```python
is_source_supported("Java", "Built JavaScript applications")  # True; expected False
is_source_supported("C", "Cloud systems")                     # True; expected False
```

This affects AI-parsed skills and every other parsed field checked by this helper. It
violates the central requirement that generated or extracted facts must be supported by
the user's source material.

**Required change**

- Replace substring matching with the shared boundary-aware implementation in
  `backend/app/services/text_matching.py`.
- Preserve case-insensitive Unicode normalization and support legitimate phrases and
  technical tokens such as `C++`, `C#`, `.NET`, and hyphenated terms.
- Do not introduce a second matching algorithm in `grounding.py`.

**Regression coverage**

- Reject `Java` when only `JavaScript` is present.
- Reject `C` when only an unrelated word containing `c` is present.
- Reject `AI` when only a word such as `chair` is present.
- Accept exact and case-insensitive whole-term matches.
- Cover multi-word phrases and the technical tokens listed above.
- Exercise `ground_parsed_resume`, not only the low-level helper.

**Acceptance criteria**

- No parsed skill, credential, employer, role, date, project, or certification survives
  grounding solely because it is a substring of an unrelated source word.
- Existing valid grounding tests continue to pass.

### 2. Fix deletion of the current resume version

**Problem**

`backend/app/api/routes/resumes.py:delete_resume_version` sets a replacement version's
`is_current` flag before the current version is deleted. SQLAlchemy flushes the update
while the old current row still exists, violating the partial unique index
`uq_resume_versions_resume_current`.

Confirmed result against PostgreSQL: `UniqueViolation` when deleting a current version
that has a replacement.

**Required change**

- Clear or delete the old current row and flush that change before marking the
  replacement current.
- Keep the operation in one transaction.
- Preserve the rule that the last remaining version cannot be deleted.
- Ensure a failed transition rolls back without leaving a resume with zero or multiple
  current versions.

**Regression coverage**

- Delete a non-current version.
- Delete the current version when another version exists.
- Reject deletion of the last version.
- Assert exactly one current version after each successful operation.
- Run these tests against PostgreSQL so the production partial index is exercised.

**Acceptance criteria**

- Deleting the current version returns `204` and deterministically promotes the newest
  remaining version.
- No unique-constraint error reaches the user.

### 3. Upgrade vulnerable frontend production dependencies

**Problem**

On 2026-09-15, `npm audit --omit=dev` reported five vulnerable production dependency
packages: one critical, three high, and one moderate. The direct dependency
`next@16.2.9` is affected, and npm currently recommends `next@16.3.5`.

**Required change**

- Upgrade `next` and `eslint-config-next` together to a patched compatible release.
- Refresh the lockfile without using `npm audit fix --force`.
- Review and update the remaining transitive `nanoid`, `postcss`, `sharp`, and
  `baseline-browser-mapping` paths through normal dependency resolution.
- Re-read the installed Next.js documentation under `frontend/node_modules/next/dist/docs/`
  before adapting code for version-specific behavior.

**Acceptance criteria**

- `npm audit --omit=dev` has no known high or critical findings.
- Frontend lint, type checking, production build, and Playwright workflows pass.
- Authentication redirects and same-origin Caddy routing behave as before.

## P1 — Product Clarity And Regression Safety

### 4. Represent non-applicable score categories honestly

**Problem**

The backend normalizes the overall score across applicable category weights. The
frontend still renders every category against fixed maxima of `35/30/20/10/5`.
Consequently, an overall score can be correct while the visible category breakdown does
not add up to that score. A zero also cannot tell the UI whether the category was
applicable and missed or not applicable at all.

**Required change**

- Extend the analysis response with explicit applicability metadata for each category,
  preferably a breakdown containing `earned`, `maximum`, and `applicable`.
- Render non-applicable categories as `N/A`, not `0/max`.
- Explain that the overall percentage is normalized across applicable requirements.
- Do not infer applicability in the frontend from a zero score.

**Acceptance criteria**

- The UI can explain how every overall score was calculated.
- A job without an education requirement shows education as `N/A`.
- A required category with no matching evidence still shows `0/max`.
- Backend and frontend regression tests cover both cases.

### 5. Handle analyses created before grounded scoring

**Problem**

Previously stored analyses retain their original provider, explanation, and AI-authored
recommendations. They remain visible after the merge and may look like current grounded
guidance even though they were created under the old behavior.

**Required change**

- Identify legacy analyses using provider/model or an explicit analysis-version field.
- Clearly label legacy results and offer an explicit “Run updated analysis” action.
- Do not silently overwrite historical user data.
- Prefer persisting a matcher/analysis version on every new result.

**Acceptance criteria**

- No legacy AI recommendation is presented as newly grounded output without a warning.
- Re-running creates a versioned deterministic result while preserving the historical
  record for auditability.

### 6. Add E2E coverage for the remediated business workflows

**Problem**

The current E2E suite verifies the broad workspace loop but does not assert several
behaviors introduced by PR #44.

**Required scenarios**

- Job detail changes from **Track application** to **View tracker** after tracking.
- Resume and cover-letter selectors only permit coherent material combinations.
- Selecting a cover letter derives or validates its linked resume.
- Moving to `applied` records `applied_at`; later workflow stages do not clear it.
- Generating materials advances preparation stages but never regresses interviews or
  outcomes.
- Dashboard applied count is cumulative from `applied_at`, not only current status.
- Duplicate job creation is rejected and a duplicate discovery save reuses the saved
  job.
- Settings display the authenticated account and actual configured providers.

Tests must create unique data, clean it up, and remain safe under Playwright retries.

### 7. Synchronize the durable design documentation

**Problem**

`docs/design.md` still describes the old `30/25/20/10/5/10` weighting, including
formatting as job fit. The implementation and issue #42 intentionally use
`35/30/20/10/5`, exclude formatting from fit, and normalize across applicable
categories.

**Required change**

- Update `docs/design.md` and `docs/architecture.md` to describe the implemented scoring
  model and deterministic recommendations.
- Explain applicability normalization and the difference between formatting quality and
  job fit.
- Document analysis-version and legacy-result behavior when item 5 is implemented.

## P2 — Maintainability And Delivery Decisions

### 8. Guard migration/runtime job-identity equivalence

The job identity migration intentionally contains a frozen copy of normalization and
hashing logic, while runtime behavior lives in `backend/app/services/job_identity.py`.
Do not import mutable application code into an old migration. Instead, add equivalence
fixtures proving both implementations produce identical keys for canonical URLs,
tracking parameters, Unicode/case differences, and company/title/location fallbacks.

### 9. Remove obsolete provider plumbing from deterministic analysis

`analyze_resume_for_job` is asynchronous and receives an AI provider even though it no
longer calls the provider. Make the service synchronous, remove the unused parameter,
and simplify provider metadata without changing stored compatibility fields.

### 10. Centralize application material-selection behavior

The create and edit forms duplicate resume/cover-letter filtering and coupled selection
logic. Extract one small shared hook or component so both paths enforce the same
compatibility rules.

### 11. Reduce coordination inside the jobs route module

Move tailored-resume generation and saved-job identity coordination behind focused
services. Route handlers should authenticate, validate request ownership, call one
business operation, and shape the response.

### 12. Confirm the GHCR publication policy

PR #44 added container publication with `packages: write`. Decide and document whether
publishing images from `main` is part of the intended release process. If it is, document
image retention, tags, permissions, and rollback. If it is not, remove the publication
jobs and associated permissions.

## Recommended Delivery Order

1. Grounding boundaries and current-version deletion, with regression tests.
2. Next.js and transitive production dependency upgrades.
3. Score applicability contract and UI.
4. Legacy-analysis labeling/versioning.
5. Expanded E2E coverage and scoring documentation.
6. Maintainability work, kept in separate focused changes where practical.

## Definition Of Done

The follow-up is complete when:

- All P0 and P1 acceptance criteria pass.
- Backend Ruff and the full pytest suite pass against PostgreSQL.
- Frontend lint, type checking, build, and dependency audit pass.
- Docker Compose upgrades an existing database and starts every required service.
- Desktop and mobile Playwright workflows pass with no application console errors.
- Alembic upgrade, downgrade/re-upgrade, and schema-drift checks pass.
- Documentation matches the shipped scoring and release behavior.
- No external email, outreach, or job application is sent without explicit user action.
