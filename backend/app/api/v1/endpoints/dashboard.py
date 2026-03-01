"""Dashboard statistics endpoints."""

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.assignment import Assignment
from app.models.grading import GradingResult, QuestionFeedback
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregate statistics for the dashboard."""

    # Total assignments
    total_q = await db.execute(select(func.count(Assignment.id)))
    total_assignments = total_q.scalar() or 0

    # Grading results counts
    pending_q = await db.execute(
        select(func.count(GradingResult.id)).where(
            GradingResult.status == "ai_graded"
        )
    )
    pending_grading = pending_q.scalar() or 0

    completed_q = await db.execute(
        select(func.count(GradingResult.id)).where(
            GradingResult.status.in_(["teacher_reviewed", "finalized"])
        )
    )
    completed = completed_q.scalar() or 0

    # Average score percentage
    avg_q = await db.execute(
        select(
            func.avg(
                case(
                    (
                        and_(
                            GradingResult.total_possible > 0,
                            GradingResult.total_score.isnot(None),
                        ),
                        GradingResult.total_score * 100.0 / GradingResult.total_possible,
                    ),
                    else_=None,
                )
            )
        )
    )
    avg_score = avg_q.scalar()
    avg_score = round(float(avg_score), 1) if avg_score is not None else 0.0

    # Grade distribution (buckets: 0-10, 10-20, ..., 90-100)
    grade_distribution = []
    for low in range(0, 100, 10):
        high = low + 10
        label = f"{low}-{high}%"
        cnt_q = await db.execute(
            select(func.count(GradingResult.id)).where(
                and_(
                    GradingResult.total_possible > 0,
                    GradingResult.total_score.isnot(None),
                    (GradingResult.total_score * 100.0 / GradingResult.total_possible) >= low,
                    (GradingResult.total_score * 100.0 / GradingResult.total_possible)
                    < (high if high < 100 else 101),
                )
            )
        )
        grade_distribution.append({"range": label, "count": cnt_q.scalar() or 0})

    # Knowledge point heatmap — top 5 most frequent errors from question_feedbacks
    # knowledge_points is a JSONB column
    kp_q = await db.execute(
        select(
            QuestionFeedback.error_type,
            func.count(QuestionFeedback.id).label("cnt"),
        )
        .where(
            QuestionFeedback.error_type.isnot(None),
            QuestionFeedback.error_type != "none",
        )
        .group_by(QuestionFeedback.error_type)
        .order_by(func.count(QuestionFeedback.id).desc())
        .limit(5)
    )
    knowledge_heatmap = [
        {
            "topic": row.error_type.replace("_", " ").title(),
            "error_count": row.cnt,
            "module": "General",
        }
        for row in kp_q.all()
    ]

    # Monthly progress for last 6 months
    now = datetime.now(timezone.utc)
    monthly_progress = []
    for i in range(5, -1, -1):
        month_start = (now - relativedelta(months=i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + relativedelta(months=1))
        label = month_start.strftime("%b %Y")

        graded_q = await db.execute(
            select(func.count(GradingResult.id)).where(
                and_(
                    GradingResult.graded_at >= month_start,
                    GradingResult.graded_at < month_end,
                    GradingResult.status.in_(["teacher_reviewed", "finalized"]),
                )
            )
        )
        pending_m_q = await db.execute(
            select(func.count(GradingResult.id)).where(
                and_(
                    GradingResult.graded_at >= month_start,
                    GradingResult.graded_at < month_end,
                    GradingResult.status == "ai_graded",
                )
            )
        )
        monthly_progress.append(
            {
                "month": label,
                "graded": graded_q.scalar() or 0,
                "pending": pending_m_q.scalar() or 0,
            }
        )

    return {
        "total_assignments": total_assignments,
        "pending_grading": pending_grading,
        "completed": completed,
        "total_students": 0,
        "avg_score": avg_score,
        "grade_distribution": grade_distribution,
        "knowledge_heatmap": knowledge_heatmap,
        "monthly_progress": monthly_progress,
    }
