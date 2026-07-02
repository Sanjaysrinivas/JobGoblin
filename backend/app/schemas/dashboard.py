import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummaryOut(BaseModel):
    saved: int
    applied: int
    interviewing: int
    offers: int
    follow_ups_due: int
    avg_score: float | None = None


class ActivityEventOut(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    event_type: str
    description: str | None = None
    metadata: dict | None = Field(default=None)
    created_at: datetime
