# AI Resume Editing Plan

This document describes the review-only resume editing workflow for tailoring an
uploaded resume to a specific job.

## Goal

Let a user create a tailored copy of an uploaded resume for one job, apply
grounded AI edits to that copy, review the changes, and download the edited
resume.

The app must never overwrite the original uploaded resume. The original upload
remains the source of truth for provenance and recovery.

## User Flow

1. User uploads a resume.
2. User saves or opens a target job.
3. User runs resume-to-job analysis.
4. If the resume can be improved, the job page shows a button:
   `Create tailored copy`.
5. The backend creates a non-current `ResumeVersion` linked to the job and the
   source resume version.
6. AI rewrites only grounded sections: summary, skills ordering, experience
   bullets, projects, and role framing.
7. The UI shows the tailored copy with change notes and grounding evidence.
8. User can accept, reject, edit manually, or download the tailored copy.
9. Accepting the copy can mark it as the current version for that resume.

## Product Rules

- Original uploaded files are immutable.
- AI may reword, reorder, emphasize, and condense existing facts.
- AI may add a keyword only when the resume already contains matching evidence.
- AI must not invent employers, roles, tools, dates, degrees, certifications,
  metrics, responsibilities, or eligibility claims.
- Every material rewrite should keep grounding metadata that points back to
  source resume content or matched analysis evidence.
- Download/export is local only. The app must not submit applications, send
  emails, or post to external services.

## Existing Pieces To Reuse

- `resumes`: original upload metadata, extracted text, parsed JSON, default flag.
- `resume_versions`: editable copies, current flag, source version, job link,
  extracted text, parsed JSON, and export path.
- `job_analyses`: score, matched keywords, missing keywords, recommendations,
  application readiness, checklist, and rewrite suggestions.
- `POST /api/jobs/{job_id}/resume-drafts`: existing tailored draft creation.
- `GET /api/jobs/{job_id}/resume-drafts`: list job-linked drafts.
- `PATCH /api/resumes/{resume_id}/versions/{version_id}`: manual edits.
- `POST /api/resumes/{resume_id}/versions/{version_id}/make-current`: accept.
- `GET /api/resumes/{resume_id}/versions/{version_id}/export.pdf`: download.

## Backend Shape

Keep `ResumeVersion` as the tailored copy surface. Avoid a new table unless
review state grows beyond what `parsed_json` metadata can represent.

Recommended draft metadata inside `ResumeVersion.parsed_json`:

```json
{
  "tailoring": {
    "job_id": "uuid",
    "source_version_id": "uuid",
    "analysis_id": "uuid",
    "status": "draft",
    "grounding": {
      "matched_existing_terms": ["Python", "stakeholder management"],
      "missing_terms_not_added": ["Kubernetes"]
    },
    "changes": [
      {
        "section": "summary",
        "action": "rewrite",
        "before": "Original summary text",
        "after": "Tailored summary text",
        "evidence": ["Original summary text", "Python"]
      }
    ]
  }
}
```

The AI prompt should receive:

- source resume version text and parsed JSON
- target job title, company, description, and work mode
- latest analysis fields
- profile facts, if available
- explicit no-fabrication rules

The response should be structured JSON with edited resume sections, change
notes, and grounding. If grounding is missing or malformed, the backend should
fall back to a conservative copy with recommendations only.

## Frontend Shape

Job detail should expose this workflow near resume-to-job analysis:

- `Create tailored copy` when analysis exists and a resume is selected.
- Tailored copy list scoped to the job.
- Diff/review panel with original vs edited sections.
- Controls: `Apply edits`, `Edit manually`, `Reject`, `Download PDF`.
- Clear badge when a draft is grounded, missing evidence, or needs review.

The button text should avoid implying that the original upload is modified.
Use `Create tailored copy` before generation and `Apply edits` only inside the
copy review flow.

## Acceptance Criteria

- Creating a tailored copy never changes the original `resumes` row or uploaded
  file.
- The copy is linked to `job_id` and `source_version_id`.
- Unsupported missing keywords are listed as not added.
- User can review the generated copy before making it current.
- User can download the tailored copy as PDF.
- Tests prove ownership checks, no source overwrite, grounded metadata, accept,
  reject, and export behavior.

## Non-Goals

- Editing PDFs in place.
- Auto-applying to jobs.
- Sending resumes to employers.
- Scraping LinkedIn, Indeed, or employer sites.
- Generating unsupported claims to increase the match score.
