from app.models import Job, Profile, Resume, ResumeVersion


def _lines(text: str | None, limit: int) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()][:limit]


def _profile_lines(profile: Profile | None) -> list[str]:
    if profile is None:
        return []
    lines = _lines(profile.summary, 2)
    if profile.headline:
        lines.append(profile.headline)
    if profile.skills:
        lines.append("Skills: " + ", ".join(profile.skills[:8]))
    for item in (profile.experience or [])[:2]:
        if isinstance(item, dict):
            role = item.get("role")
            company = item.get("company")
            highlights = item.get("highlights") or []
            if role or company:
                lines.append(" ".join(str(part) for part in [role, company] if part))
            lines.extend(str(highlight) for highlight in highlights[:2])
    lines.extend(profile.projects[:2] if profile.projects else [])
    return [line for line in lines if line][:6]


def generate_interview_questions(
    job: Job,
    resume: Resume | None = None,
    version: ResumeVersion | None = None,
    profile: Profile | None = None,
    application_notes: str | None = None,
    prep_notes: str | None = None,
) -> list[dict]:
    source_text = (
        version.extracted_text if version else resume.extracted_text if resume else ""
    ) or ""
    evidence = _lines(source_text, 3)
    evidence.extend(_profile_lines(profile))
    evidence.extend(_lines(application_notes, 2))
    evidence.extend(_lines(prep_notes, 2))
    if not evidence:
        evidence = [job.title, job.company_name]
    evidence = evidence[:8]

    return [
        {
            "question": f"How would you approach the {job.title} role at {job.company_name}?",
            "category": "role_fit",
            "why": "Tests whether the candidate understands the role and company context.",
            "answer_outline": (
                "Connect the job requirements to the strongest evidence above, then "
                "describe a practical first-90-days plan."
            ),
            "evidence": evidence,
        },
        {
            "question": (
                "Tell me about a project that proves you can handle this role's "
                "core responsibilities."
            ),
            "category": "experience",
            "why": "Prompts a concrete story grounded in the resume.",
            "answer_outline": (
                "Use situation, action, result, and name the tools or decisions "
                "that map to the job description."
            ),
            "evidence": evidence,
        },
        {
            "question": "Which STAR story should you keep ready for this interview?",
            "category": "story_bank",
            "why": "Builds a reusable story bank grounded in existing notes and resume evidence.",
            "answer_outline": (
                "Pick one concrete story. Situation: context and stakes. Task: your "
                "responsibility. Action: decisions you made. Result: measurable outcome "
                "or lesson learned. Tie the result back to this role."
            ),
            "evidence": evidence[:5],
        },
        {
            "question": "What questions would you ask the team before accepting this job?",
            "category": "candidate_questions",
            "why": "Checks judgment, priorities, and preparation.",
            "answer_outline": (
                "Ask about success metrics, team process, technical constraints, "
                "and hiring timeline."
            ),
            "evidence": [job.description[:240]],
        },
    ]
