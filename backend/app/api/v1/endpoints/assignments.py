"""Assignment CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.assignment import Assignment
from app.models.user import User
from app.schemas.assignment import AssignmentCreate, AssignmentResponse

router = APIRouter()


@router.post("/", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Create a new assignment."""
    assignment = Assignment(
        title=body.title,
        description=body.description,
        classroom_id=body.classroom_id,
        created_by=current_user.id,
        mark_scheme_id=body.mark_scheme_id,
        subject_id=body.subject_id,
        total_marks=body.total_marks,
        due_date=body.due_date,
        status="draft",
    )
    db.add(assignment)
    await db.flush()
    return AssignmentResponse.model_validate(assignment)


@router.get("/", response_model=list[AssignmentResponse])
async def list_assignments(
    classroom_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List assignments, optionally filtered by classroom."""
    query = select(Assignment).order_by(Assignment.created_at.desc())
    if classroom_id:
        query = query.where(Assignment.classroom_id == classroom_id)
    result = await db.execute(query)
    return [AssignmentResponse.model_validate(a) for a in result.scalars().all()]


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single assignment by ID."""
    result = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return AssignmentResponse.model_validate(assignment)


@router.patch("/{assignment_id}/publish", response_model=AssignmentResponse)
async def publish_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Publish a draft assignment to make it visible to students."""
    result = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    assignment.status = "published"
    await db.flush()
    return AssignmentResponse.model_validate(assignment)
