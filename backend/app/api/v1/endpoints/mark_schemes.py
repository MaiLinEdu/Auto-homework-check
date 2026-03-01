"""Mark scheme CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.mark_scheme import MarkScheme, MarkSchemeVersion
from app.models.user import User

router = APIRouter()


# --- Schemas (local to keep it self-contained) ---
class MarkSchemeCreateRequest(BaseModel):
    title: str
    subject_id: uuid.UUID | None = None
    curriculum_system_id: uuid.UUID | None = None
    total_marks: int | None = None
    content: dict  # The actual mark scheme data (JSON)


class MarkSchemeUpdateRequest(BaseModel):
    title: str | None = None
    total_marks: int | None = None
    content: dict | None = None
    change_description: str | None = None


class MarkSchemeResponse(BaseModel):
    id: uuid.UUID
    title: str
    subject_id: uuid.UUID | None
    curriculum_system_id: uuid.UUID | None
    is_official: bool
    total_marks: int | None
    current_version: int
    created_at: str

    model_config = {"from_attributes": True}


# --- Endpoints ---
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=MarkSchemeResponse)
async def create_mark_scheme(
    body: MarkSchemeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Create a new mark scheme with its first version."""
    scheme = MarkScheme(
        title=body.title,
        subject_id=body.subject_id,
        curriculum_system_id=body.curriculum_system_id,
        total_marks=body.total_marks,
        created_by=current_user.id,
        current_version=1,
    )
    db.add(scheme)
    await db.flush()

    version = MarkSchemeVersion(
        mark_scheme_id=scheme.id,
        version_number=1,
        content=body.content,
        change_description="Initial version",
    )
    db.add(version)
    return MarkSchemeResponse.model_validate(scheme)


@router.get("/", response_model=list[MarkSchemeResponse])
async def list_mark_schemes(
    subject_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List mark schemes, optionally filtered by subject."""
    stmt = select(MarkScheme)
    if subject_id:
        stmt = stmt.where(MarkScheme.subject_id == subject_id)
    result = await db.execute(stmt.order_by(MarkScheme.created_at.desc()))
    return [MarkSchemeResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/{scheme_id}", response_model=MarkSchemeResponse)
async def get_mark_scheme(
    scheme_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single mark scheme."""
    result = await db.execute(select(MarkScheme).where(MarkScheme.id == scheme_id))
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=404, detail="Mark scheme not found")
    return MarkSchemeResponse.model_validate(scheme)


@router.patch("/{scheme_id}", response_model=MarkSchemeResponse)
async def update_mark_scheme(
    scheme_id: uuid.UUID,
    body: MarkSchemeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("teacher", "school_admin", "super_admin")),
):
    """Update a mark scheme, creating a new version if content changed."""
    result = await db.execute(
        select(MarkScheme).where(MarkScheme.id == scheme_id)
    )
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=404, detail="Mark scheme not found")

    if body.title is not None:
        scheme.title = body.title
    if body.total_marks is not None:
        scheme.total_marks = body.total_marks

    if body.content is not None:
        scheme.current_version += 1
        version = MarkSchemeVersion(
            mark_scheme_id=scheme.id,
            version_number=scheme.current_version,
            content=body.content,
            change_description=body.change_description or "",
        )
        db.add(version)

    await db.flush()
    return MarkSchemeResponse.model_validate(scheme)
