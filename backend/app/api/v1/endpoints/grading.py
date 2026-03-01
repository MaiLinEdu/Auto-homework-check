"""Grading endpoints: trigger AI grading, view results, teacher review, report generation."""

import logging
import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
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

logger = logging.getLogger(__name__)

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


# --- Grading Queue (for the /grading list page) ---


@router.get("/queue")
async def get_grading_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Return all grading results as a queue for the teacher grading list."""
    result = await db.execute(
        select(GradingResult).order_by(GradingResult.graded_at.desc()).limit(100)
    )
    items = result.scalars().all()

    queue = []
    for gr in items:
        queue.append(
            {
                "id": str(gr.id),
                "submission_id": str(gr.submission_id),
                "student_name": "Student",  # would join with submission -> user
                "assignment_title": "Assignment",  # would join with submission -> assignment
                "submitted_at": gr.graded_at.isoformat() if gr.graded_at else "",
                "status": gr.status,
                "total_score": gr.total_score,
                "total_possible": gr.total_possible,
            }
        )
    return queue


# --- AI Parent Feedback Report Generation (Qiran Model) ---


class GenerateReportRequest(BaseModel):
    grading_result_id: str
    student_name: str = "Student"
    subject: str = "General"
    language: str = "bilingual"  # bilingual, en, zh


@router.post("/generate-report")
async def generate_parent_report(
    body: GenerateReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Generate a Qiran-style parent feedback report using LLM."""
    result = await db.execute(
        select(GradingResult)
        .options(selectinload(GradingResult.question_feedbacks))
        .where(GradingResult.id == uuid.UUID(body.grading_result_id))
    )
    grading = result.scalar_one_or_none()
    if not grading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grading result not found",
        )

    # Build context from question feedbacks
    wrong_answers = []
    for qf in grading.question_feedbacks:
        if qf.error_type and qf.error_type != "none":
            wrong_answers.append(
                {
                    "question": qf.question_number,
                    "error_type": qf.error_type,
                    "error_analysis": qf.error_analysis or "",
                    "knowledge_points": qf.knowledge_points or {},
                    "score": qf.score,
                    "max_score": qf.max_score,
                    "improvement": qf.improvement_suggestions or "",
                }
            )

    student_score = float(grading.total_score or 0)
    total_possible = float(grading.total_possible or 100)

    # Compute class-level statistics for percentile
    stats_q = await db.execute(
        select(
            func.avg(GradingResult.total_score).label("mean"),
            func.stddev(GradingResult.total_score).label("std"),
        ).where(GradingResult.total_possible == grading.total_possible)
    )
    stats_row = stats_q.first()
    mean_score = float(stats_row.mean) if stats_row and stats_row.mean else student_score
    std_dev = float(stats_row.std) if stats_row and stats_row.std else total_possible * 0.15

    # Compute percentile
    if std_dev > 0:
        z = (student_score - mean_score) / std_dev
        percentile = _normal_cdf(z) * 100
    else:
        percentile = 50.0

    # Build LLM prompt for Qiran-style report
    import json

    wrong_answers_str = json.dumps(wrong_answers, indent=2, ensure_ascii=False)

    system_prompt = f"""You are an experienced international curriculum teacher generating a parent feedback report.

Follow the "Qiran Template" feedback style:
- Structure: Performance Summary + Core Error Analysis + Targeted Suggestions for Improvement
- Tone: Professional, objective, yet encouraging
- Language: {"Bilingual output — Chinese for narrative sections (for parents), English for specific academic terminology" if body.language == "bilingual" else body.language}

Student: {body.student_name}
Subject: {body.subject}
Score: {student_score}/{total_possible} ({student_score/total_possible*100:.1f}%)
Percentile: {percentile:.0f}th

Errors found:
{wrong_answers_str}

Generate a report with exactly three sections:
1. PERFORMANCE_SUMMARY: A 2-3 paragraph overview of the student's performance
2. CORE_ERROR_ANALYSIS: Detailed analysis of each error, referencing specific knowledge points (e.g., Atomic Structure, Mechanics, Binomial Expansion)
3. IMPROVEMENT_SUGGESTIONS: Concrete, actionable recommendations for improvement

Return JSON with keys: performance_summary, core_error_analysis, improvement_suggestions"""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": system_prompt}],
        )
        response_text = message.content[0].text

        # Parse JSON from response
        import re

        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            report_data = json.loads(json_match.group())
        else:
            report_data = {
                "performance_summary": response_text,
                "core_error_analysis": "",
                "improvement_suggestions": "",
            }
    except Exception as e:
        logger.warning("LLM report generation failed: %s", e)
        # Fallback: generate structured report from data
        report_data = {
            "performance_summary": (
                f"{body.student_name} scored {student_score}/{total_possible} "
                f"({student_score/total_possible*100:.1f}%), placing at the "
                f"{percentile:.0f}th percentile. "
                f"{'The student demonstrated strong overall understanding.' if percentile > 60 else 'There are areas that need focused attention.'}"
            ),
            "core_error_analysis": "\n".join(
                f"- Q{wa['question']}: {wa['error_type']} error — {wa['error_analysis']}"
                for wa in wrong_answers
            )
            or "No significant errors identified.",
            "improvement_suggestions": "\n".join(
                f"- Q{wa['question']}: {wa['improvement']}"
                for wa in wrong_answers
                if wa["improvement"]
            )
            or "Continue with current study approach.",
        }

    return {
        "performance_summary": report_data.get("performance_summary", ""),
        "core_error_analysis": report_data.get("core_error_analysis", ""),
        "improvement_suggestions": report_data.get("improvement_suggestions", ""),
        "percentile": round(percentile, 1),
        "mean_score": round(mean_score, 1),
        "std_dev": round(std_dev, 1),
        "student_score": student_score,
        "total_possible": total_possible,
    }


def _normal_cdf(z: float) -> float:
    """Approximate the standard normal CDF."""
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    d = 0.3989422804014327
    p = d * math.exp(-z * z / 2.0) * (
        t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    )
    return 1.0 - p if z > 0 else p
