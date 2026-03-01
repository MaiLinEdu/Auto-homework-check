"""Submission endpoints: upload, list, view."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.assignment import AssignmentSubmission
from app.models.user import User
from app.schemas.assignment import SubmissionResponse
from app.services.storage import StorageService
from app.tasks.processing import process_submission_task

router = APIRouter()


@router.post("/", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    assignment_id: uuid.UUID,
    files: list[UploadFile] = File(default=[]),
    raw_text: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit an assignment with optional file uploads and/or text input."""
    file_urls = {}
    storage = StorageService()
    for f in files:
        url = await storage.upload_file(f, prefix=f"submissions/{assignment_id}")
        file_urls[f.filename] = url

    submission = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        status="submitted",
        file_urls=file_urls if file_urls else None,
        raw_text=raw_text,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    await db.flush()

    # Queue async OCR + preprocessing
    process_submission_task.delay(str(submission.id))

    return SubmissionResponse.model_validate(submission)


@router.get("/", response_model=list[SubmissionResponse])
async def list_submissions(
    assignment_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List submissions. Teachers see all; students see only their own."""
    query = select(AssignmentSubmission).order_by(
        AssignmentSubmission.created_at.desc()
    )
    if assignment_id:
        query = query.where(AssignmentSubmission.assignment_id == assignment_id)
    if current_user.role == "student":
        query = query.where(AssignmentSubmission.student_id == current_user.id)
    result = await db.execute(query)
    return [SubmissionResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single submission by ID."""
    result = await db.execute(
        select(AssignmentSubmission).where(AssignmentSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return SubmissionResponse.model_validate(submission)
