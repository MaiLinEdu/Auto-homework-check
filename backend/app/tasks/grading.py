"""Async task for AI grading."""

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.core.config import settings
from app.models.assignment import AssignmentSubmission
from app.models.grading import GradingResult, QuestionFeedback
from app.models.mark_scheme import MarkScheme, MarkSchemeVersion
from app.services.ai.grader import AIGrader
from app.worker import celery_app

sync_engine = create_engine(settings.database_url_sync)


@celery_app.task(bind=True, max_retries=3)
def grade_submission_task(self, submission_id: str, mark_scheme_id: str | None = None):
    """Grade a submission using the AI engine."""
    with Session(sync_engine) as db:
        submission = db.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.id == submission_id
            )
        ).scalar_one_or_none()

        if not submission:
            return {"error": "Submission not found"}

        if not submission.separated_content or not submission.separated_content.get("items"):
            return {"error": "No separated content available — run OCR processing first"}

        # Load mark scheme
        mark_scheme_content = {}
        if mark_scheme_id:
            ms = db.execute(
                select(MarkScheme).where(MarkScheme.id == mark_scheme_id)
            ).scalar_one_or_none()
            if ms:
                latest_version = db.execute(
                    select(MarkSchemeVersion)
                    .where(MarkSchemeVersion.mark_scheme_id == ms.id)
                    .order_by(MarkSchemeVersion.version_number.desc())
                ).scalars().first()
                if latest_version:
                    mark_scheme_content = latest_version.content

        submission.status = "processing"
        db.commit()

        try:
            grader = AIGrader()
            questions = submission.separated_content["items"]

            grading_output = asyncio.get_event_loop().run_until_complete(
                grader.grade_submission(
                    questions=questions,
                    mark_scheme=mark_scheme_content,
                    subject_category="stem_calculation",
                )
            )

            # Persist results
            grading_result = GradingResult(
                submission_id=submission.id,
                total_score=grading_output.total_score,
                total_possible=grading_output.total_possible,
                overall_feedback=grading_output.overall_feedback,
                confidence_score=grading_output.confidence,
                needs_review=grading_output.confidence < 0.7,
                status="ai_graded",
            )
            db.add(grading_result)
            db.flush()

            for qg in grading_output.question_grades:
                feedback = QuestionFeedback(
                    grading_result_id=grading_result.id,
                    question_number=qg.question_number,
                    question_text=next(
                        (q["question_text"] for q in questions if q["question_number"] == qg.question_number),
                        "",
                    ),
                    student_answer=next(
                        (q["student_answer"] for q in questions if q["question_number"] == qg.question_number),
                        "",
                    ),
                    score=qg.score,
                    max_score=qg.max_score,
                    scoring_rationale=qg.scoring_rationale,
                    error_analysis=qg.error_analysis,
                    error_type=qg.error_type,
                    model_solution=qg.model_solution,
                    improvement_suggestions=qg.improvement_suggestions,
                    knowledge_points={"tags": qg.knowledge_points},
                    confidence=qg.confidence,
                )
                db.add(feedback)

            submission.status = "graded"
            db.commit()

            return {
                "status": "success",
                "total_score": grading_output.total_score,
                "total_possible": grading_output.total_possible,
                "confidence": grading_output.confidence,
            }

        except Exception as exc:
            submission.status = "submitted"
            db.commit()
            raise self.retry(exc=exc, countdown=60)
