"""Async task for AI grading.

Reads the separated content from a processed submission, resolves the
mark scheme + subject category, invokes the AI grader, and persists
structured results (including per-criterion breakdowns and method marks).
"""

import asyncio
import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.curriculum import Subject
from app.models.grading import GradingResult, QuestionFeedback
from app.models.mark_scheme import MarkScheme, MarkSchemeVersion
from app.services.ai.grader import AIGrader
from app.worker import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)

REVIEW_CONFIDENCE_THRESHOLD = 0.70


def _run_async(coro):
    """Run an async coroutine from synchronous Celery context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _resolve_subject_category(db: Session, submission: AssignmentSubmission) -> str:
    """Determine the subject category from the assignment's linked subject."""
    if not submission.assignment_id:
        return "stem_calculation"

    assignment = db.execute(
        select(Assignment).where(Assignment.id == submission.assignment_id)
    ).scalar_one_or_none()
    if not assignment or not assignment.subject_id:
        return "stem_calculation"

    subject = db.execute(
        select(Subject).where(Subject.id == assignment.subject_id)
    ).scalar_one_or_none()

    return subject.category if subject and subject.category else "stem_calculation"


@celery_app.task(
    bind=True,
    name="grading.grade_submission",
    queue="grading",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def grade_submission_task(self, submission_id: str, mark_scheme_id: str | None = None):
    """Grade a submission using the AI engine."""
    with Session(sync_engine) as db:
        submission = db.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.id == submission_id
            )
        ).scalar_one_or_none()

        if not submission:
            logger.error("Submission %s not found", submission_id)
            return {"error": "Submission not found"}

        if not submission.separated_content or not submission.separated_content.get("items"):
            logger.error("Submission %s has no separated content", submission_id)
            return {"error": "No separated content — run OCR processing first"}

        # ── Resolve mark scheme ────────────────────────────────────────────
        mark_scheme_content: dict = {}

        # Try explicit mark_scheme_id first, then fall back to assignment's default
        effective_ms_id = mark_scheme_id
        if not effective_ms_id and submission.assignment_id:
            assignment = db.execute(
                select(Assignment).where(Assignment.id == submission.assignment_id)
            ).scalar_one_or_none()
            if assignment and assignment.mark_scheme_id:
                effective_ms_id = str(assignment.mark_scheme_id)

        if effective_ms_id:
            ms = db.execute(
                select(MarkScheme).where(MarkScheme.id == effective_ms_id)
            ).scalar_one_or_none()
            if ms:
                latest_version = db.execute(
                    select(MarkSchemeVersion)
                    .where(MarkSchemeVersion.mark_scheme_id == ms.id)
                    .order_by(MarkSchemeVersion.version_number.desc())
                ).scalars().first()
                if latest_version:
                    mark_scheme_content = latest_version.content

        # ── Resolve subject category ───────────────────────────────────────
        subject_category = _resolve_subject_category(db, submission)
        logger.info(
            "Grading submission %s — category=%s, mark_scheme=%s",
            submission_id, subject_category, bool(mark_scheme_content),
        )

        submission.status = "grading"
        db.commit()

        try:
            grader = AIGrader()
            questions = submission.separated_content["items"]

            grading_output = _run_async(
                grader.grade_submission(
                    questions=questions,
                    mark_scheme=mark_scheme_content,
                    subject_category=subject_category,
                )
            )

            # ── Persist results ────────────────────────────────────────────
            needs_review = grading_output.confidence < REVIEW_CONFIDENCE_THRESHOLD
            grading_result = GradingResult(
                submission_id=submission.id,
                total_score=grading_output.total_score,
                total_possible=grading_output.total_possible,
                overall_feedback=grading_output.overall_feedback,
                confidence_score=grading_output.confidence,
                needs_review=needs_review,
                status="ai_graded",
            )
            db.add(grading_result)
            db.flush()

            # Build a lookup for original question data
            q_lookup = {q["question_number"]: q for q in questions}

            for qg in grading_output.question_grades:
                orig = q_lookup.get(qg.question_number, {})
                feedback = QuestionFeedback(
                    grading_result_id=grading_result.id,
                    question_number=qg.question_number,
                    question_text=orig.get("question_text", ""),
                    student_answer=orig.get("student_answer", ""),
                    score=qg.score,
                    max_score=qg.max_score,
                    scoring_rationale=qg.scoring_rationale,
                    error_analysis=qg.error_analysis,
                    error_type=qg.error_type.value,
                    model_solution=qg.model_solution,
                    improvement_suggestions=qg.improvement_suggestions,
                    knowledge_points={
                        "tags": qg.knowledge_points,
                        "criteria_breakdown": [
                            cb.model_dump() for cb in qg.criteria_breakdown
                        ],
                        "method_marks": [
                            mm.model_dump() for mm in qg.method_marks
                        ],
                    },
                    confidence=qg.confidence,
                )
                db.add(feedback)

            submission.status = "graded"
            db.commit()

            logger.info(
                "Submission %s graded: %.1f/%s (confidence %.2f, review=%s)",
                submission_id,
                grading_output.total_score,
                grading_output.total_possible,
                grading_output.confidence,
                needs_review,
            )

            return {
                "status": "success",
                "total_score": grading_output.total_score,
                "total_possible": grading_output.total_possible,
                "confidence": grading_output.confidence,
                "needs_review": needs_review,
                "questions_graded": len(grading_output.question_grades),
            }

        except Exception as exc:
            logger.exception("Grading failed for submission %s: %s", submission_id, exc)
            submission.status = "error"
            db.commit()
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
