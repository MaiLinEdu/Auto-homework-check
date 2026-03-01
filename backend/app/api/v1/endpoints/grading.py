"""Grading endpoints: trigger AI grading, view results, teacher review."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.grading import GradingResult, QuestionFeedback
from app.models.user import User
from app.schemas.grading import (
    GradeSubmissionRequest,
    GradingResultResponse,
    TeacherReviewRequest,
)
from app.tasks.grading import grade_submission_task

router = APIRouter()


@router.post("/grade", status_code=status.HTTP_202_ACCEPTED)
async def trigger_grading(
    body: GradeSubmissionRequest,
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Trigger AI grading for a submission (async task)."""
    grade_submission_task.delay(
        str(body.submission_id),
        str(body.mark_scheme_id) if body.mark_scheme_id else None,
    )
    return {"message": "Grading task queued", "submission_id": str(body.submission_id)}


@router.get("/results/{submission_id}", response_model=GradingResultResponse)
async def get_grading_result(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get grading results for a submission."""
    result = await db.execute(
        select(GradingResult)
        .options(selectinload(GradingResult.question_feedbacks))
        .where(GradingResult.submission_id == submission_id)
    )
    grading = result.scalar_one_or_none()
    if not grading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grading result not found",
        )
    return GradingResultResponse.model_validate(grading)


@router.post("/review/{grading_result_id}")
async def teacher_review(
    grading_result_id: uuid.UUID,
    reviews: list[TeacherReviewRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Teacher reviews and overrides AI grading for specific questions."""
    result = await db.execute(
        select(GradingResult)
        .options(selectinload(GradingResult.question_feedbacks))
        .where(GradingResult.id == grading_result_id)
    )
    grading = result.scalar_one_or_none()
    if not grading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grading result not found",
        )

    feedback_by_q = {qf.question_number: qf for qf in grading.question_feedbacks}
    for review in reviews:
        qf = feedback_by_q.get(review.question_number)
        if not qf:
            continue
        if review.teacher_score is not None:
            qf.teacher_score = review.teacher_score
        if review.teacher_feedback is not None:
            qf.teacher_feedback = review.teacher_feedback

    grading.status = "teacher_reviewed"
    grading.reviewed_by = current_user.id
    await db.flush()
    return {"message": "Review saved"}
