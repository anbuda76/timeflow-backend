from fastapi import APIRouter
from app.api.v1.endpoints import auth, organizations, users, projects, timesheets, reports, holidays, register
from app.api.v1.endpoints import weekend_auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(register.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(timesheets.router)
api_router.include_router(reports.router)
api_router.include_router(holidays.router)
api_router.include_router(weekend_auth.router)