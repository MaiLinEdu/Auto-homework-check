"""Pydantic schemas for assignment and submission operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AssignmentCreate(BaseModel):
    title: str
    description: str | None = None
    classroom_id: uuid.UUID
    mark_scheme_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    total_marks: int | None = None
    due_date: datetime | None = None


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    classroom_id: uuid.UUID
    created_by: uuid.UUID
    mark_scheme_id: uuid.UUID | None
    total_marks: int | None
    due_date: datetime | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmissionCreate(BaseModel):
    assignment_id: uuid.UUID
    raw_text: str | None = None


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    file_urls: dict | None
    ocr_result: dict | None
    submitted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
