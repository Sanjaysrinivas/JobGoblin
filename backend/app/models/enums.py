import enum


class WorkMode(enum.StrEnum):
    onsite = "onsite"
    remote = "remote"
    hybrid = "hybrid"
    unknown = "unknown"


class JobSource(enum.StrEnum):
    linkedin = "linkedin"
    company_site = "company_site"
    indeed = "indeed"
    referral = "referral"
    recruiter = "recruiter"
    other = "other"


class Priority(enum.StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class DiscoveryRunStatus(enum.StrEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class DiscoveryResultStatus(enum.StrEnum):
    new = "new"
    saved = "saved"
    dismissed = "dismissed"
    blocked = "blocked"


class ApplicationStatus(enum.StrEnum):
    saved = "saved"
    interested = "interested"
    resume_tailored = "resume_tailored"
    cover_letter_created = "cover_letter_created"
    applied = "applied"
    contacted_recruiter = "contacted_recruiter"
    referred = "referred"
    phone_screen = "phone_screen"
    technical_interview = "technical_interview"
    final_interview = "final_interview"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
    archived = "archived"


class CoverLetterTone(enum.StrEnum):
    professional = "professional"
    friendly = "friendly"
    concise = "concise"
    enthusiastic = "enthusiastic"


class CoverLetterStatus(enum.StrEnum):
    draft = "draft"
    reviewed = "reviewed"
    accepted = "accepted"
    rejected = "rejected"
    exported = "exported"


class OutreachChannel(enum.StrEnum):
    email = "email"
    linkedin = "linkedin"
    other = "other"


class OutreachStatus(enum.StrEnum):
    draft = "draft"
    copied = "copied"
    sent = "sent"
    replied = "replied"
    closed = "closed"


class InterviewPrepStatus(enum.StrEnum):
    draft = "draft"
    reviewed = "reviewed"
    ready = "ready"
    archived = "archived"
