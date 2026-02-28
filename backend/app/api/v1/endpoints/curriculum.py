"""Curriculum system and subject management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.curriculum import CurriculumSystem, Subject
from app.models.user import User

router = APIRouter()


# --- Schemas ---
class CurriculumSystemResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None

    model_config = {"from_attributes": True}


class SubjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    curriculum_system_id: uuid.UUID
    category: str

    model_config = {"from_attributes": True}


class CurriculumSystemCreateRequest(BaseModel):
    name: str
    code: str
    description: str | None = None


class SubjectCreateRequest(BaseModel):
    name: str
    code: str
    curriculum_system_id: uuid.UUID
    category: str  # stem_calculation, stem_essay, humanities_essay, data_analysis


# --- Endpoints ---
@router.get("/systems", response_model=list[CurriculumSystemResponse])
async def list_curriculum_systems(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CurriculumSystem).order_by(CurriculumSystem.name))
    return [CurriculumSystemResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/systems", status_code=status.HTTP_201_CREATED, response_model=CurriculumSystemResponse)
async def create_curriculum_system(
    body: CurriculumSystemCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("school_admin", "super_admin")),
):
    system = CurriculumSystem(name=body.name, code=body.code, description=body.description)
    db.add(system)
    await db.flush()
    return CurriculumSystemResponse.model_validate(system)


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    curriculum_system_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Subject)
    if curriculum_system_id:
        stmt = stmt.where(Subject.curriculum_system_id == curriculum_system_id)
    result = await db.execute(stmt.order_by(Subject.name))
    return [SubjectResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/subjects", status_code=status.HTTP_201_CREATED, response_model=SubjectResponse)
async def create_subject(
    body: SubjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("school_admin", "super_admin")),
):
    # Verify curriculum system exists
    result = await db.execute(
        select(CurriculumSystem).where(CurriculumSystem.id == body.curriculum_system_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Curriculum system not found")

    subject = Subject(
        name=body.name,
        code=body.code,
        curriculum_system_id=body.curriculum_system_id,
        category=body.category,
    )
    db.add(subject)
    await db.flush()
    return SubjectResponse.model_validate(subject)
