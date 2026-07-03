from app.models import Job, Resume, ResumeVersion


def generate_interview_questions(
    job: Job,
    resume: Resume | None = None,
    version: ResumeVersion | None = None,
) -> list[dict]:
    source_text = (
        version.extracted_text if version else resume.extracted_text if resume else ""
    ) or ""
    evidence = [line.strip() for line in source_text.splitlines() if line.strip()][:3]
    if not evidence:
        evidence = [job.title, job.company_name]

    return [
        {
            "question": f"How would you approach the {job.title} role at {job.company_name}?",
            "category": "role_fit",
            "why": "Tests whether the candidate understands the role and company context.",
            "answer_outline": (
                "Connect the job requirements to relevant experience, then describe a "
                "practical first-90-days plan."
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
