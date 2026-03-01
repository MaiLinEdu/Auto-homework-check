"""Seed script: populate initial curriculum systems and subjects.

Usage:
    python -m scripts.seed_data
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.models.curriculum import CurriculumSystem, Subject

CURRICULUM_SYSTEMS = [
    {"name": "International Baccalaureate", "code": "IB", "description": "IB Diploma Programme"},
    {"name": "GCE Advanced Level", "code": "A-Level", "description": "Cambridge, Edexcel, AQA"},
    {"name": "Advanced Placement", "code": "AP", "description": "College Board AP Program"},
]

# (curriculum_code, subject_name, subject_code, category)
SUBJECTS = [
    # IB
    ("IB", "Mathematics AA", "IB-MAA", "stem_calculation"),
    ("IB", "Mathematics AI", "IB-MAI", "stem_calculation"),
    ("IB", "Physics", "IB-PHY", "stem_calculation"),
    ("IB", "Chemistry", "IB-CHE", "stem_essay"),
    ("IB", "Biology", "IB-BIO", "stem_essay"),
    ("IB", "Economics", "IB-ECO", "humanities_essay"),
    ("IB", "English A", "IB-ENA", "humanities_essay"),
    ("IB", "English B", "IB-ENB", "humanities_essay"),
    ("IB", "History", "IB-HIS", "humanities_essay"),
    # A-Level
    ("A-Level", "Mathematics", "AL-MAT", "stem_calculation"),
    ("A-Level", "Further Mathematics", "AL-FMA", "stem_calculation"),
    ("A-Level", "Physics", "AL-PHY", "stem_calculation"),
    ("A-Level", "Chemistry", "AL-CHE", "stem_essay"),
    ("A-Level", "Biology", "AL-BIO", "stem_essay"),
    ("A-Level", "Economics", "AL-ECO", "humanities_essay"),
    ("A-Level", "History", "AL-HIS", "humanities_essay"),
    ("A-Level", "English Literature", "AL-ELI", "humanities_essay"),
    # AP
    ("AP", "Calculus AB", "AP-CAB", "stem_calculation"),
    ("AP", "Calculus BC", "AP-CBC", "stem_calculation"),
    ("AP", "Physics 1", "AP-PH1", "stem_calculation"),
    ("AP", "Physics 2", "AP-PH2", "stem_calculation"),
    ("AP", "Physics C: Mechanics", "AP-PCM", "stem_calculation"),
    ("AP", "Chemistry", "AP-CHE", "stem_essay"),
    ("AP", "Biology", "AP-BIO", "stem_essay"),
    ("AP", "Microeconomics", "AP-MIC", "data_analysis"),
    ("AP", "Macroeconomics", "AP-MAC", "data_analysis"),
    ("AP", "English Language", "AP-ELA", "humanities_essay"),
    ("AP", "English Literature", "AP-ELI", "humanities_essay"),
    ("AP", "US History", "AP-USH", "humanities_essay"),
    ("AP", "World History", "AP-WHI", "humanities_essay"),
]


async def seed():
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # Create curriculum systems
        cs_map: dict[str, uuid.UUID] = {}
        for cs_data in CURRICULUM_SYSTEMS:
            result = await session.execute(
                select(CurriculumSystem).where(CurriculumSystem.code == cs_data["code"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                cs_map[cs_data["code"]] = existing.id
                print(f"  Curriculum system '{cs_data['code']}' already exists, skipping.")
                continue
            cs = CurriculumSystem(id=uuid.uuid4(), **cs_data)
            session.add(cs)
            cs_map[cs_data["code"]] = cs.id
            print(f"  Created curriculum system: {cs_data['name']}")

        await session.flush()

        # Create subjects
        for cs_code, name, code, category in SUBJECTS:
            result = await session.execute(
                select(Subject).where(Subject.code == code)
            )
            if result.scalar_one_or_none():
                print(f"  Subject '{code}' already exists, skipping.")
                continue
            subject = Subject(
                id=uuid.uuid4(),
                name=name,
                code=code,
                curriculum_system_id=cs_map[cs_code],
                category=category,
            )
            session.add(subject)
            print(f"  Created subject: {name} ({code})")

        await session.commit()

    await engine.dispose()
    print("Seed data loaded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
