"""Pydantic schemas for grading results and feedback."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class QuestionFeedbackResponse(BaseModel):
    id: uuid.UUID
    question_number: str
    question_text: str | None
    student_answer: str | None
    score: float | None
    max_score: float | None
    scoring_rationale: str | None
    error_analysis: str | None
    error_type: str | None
    model_solution: str | None
    improvement_suggestions: str | None
    knowledge_points: dict | None
    confidence: float | None
    teacher_score: float | None
    teacher_feedback: str | None

    model_config = {"from_attributes": True}


class GradingResultResponse(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    total_score: float | None
    total_possible: int | None
    overall_feedback: str | None
    confidence_score: float | None
    needs_review: bool
    status: str
    graded_at: datetime
    reviewed_at: datetime | None
    question_feedbacks: list[QuestionFeedbackResponse] = []

    model_config = {"from_attributes": True}


class TeacherReviewRequest(BaseModel):
    question_number: str
    teacher_score: float | None = None
    teacher_feedback: str | None = None


class GradeSubmissionRequest(BaseModel):
    submission_id: uuid.UUID
    mark_scheme_id: uuid.UUID | None = None
