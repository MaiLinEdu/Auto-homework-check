"""Top-level API v1 router that aggregates all endpoint routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    assignments,
    curriculum,
    grading,
    mark_schemes,
    submissions,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(curriculum.router, prefix="/curriculum", tags=["Curriculum"])
api_router.include_router(mark_schemes.router, prefix="/mark-schemes", tags=["Mark Schemes"])
api_router.include_router(assignments.router, prefix="/assignments", tags=["Assignments"])
api_router.include_router(submissions.router, prefix="/submissions", tags=["Submissions"])
api_router.include_router(grading.router, prefix="/grading", tags=["Grading"])
