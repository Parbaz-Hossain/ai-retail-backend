from fastapi import APIRouter
from app.api.v1.endpoints.auth import login, register, roles, users
from app.api.v1.endpoints.hr import attendance, employees, holidays, salary, shifts
from app.api.v1.endpoints.organization import departments, locations

api_router = APIRouter()

# Authentication routes
api_router.include_router(login.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(register.router, prefix="/register", tags=["Register"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])

# Main application routes
# Organization routes
api_router.include_router(departments.router, prefix="/organization", tags=["Organization"])
api_router.include_router(locations.router, prefix="/organization", tags=["Organization"])

# HR routes
api_router.include_router(employees.router, prefix="/hr", tags=["Human Resource"])
api_router.include_router(shifts.router, prefix="/hr", tags=["Human Resource"])
api_router.include_router(attendance.router, prefix="/hr", tags=["Human Resource"])
api_router.include_router(salary.router, prefix="/hr", tags=["Human Resource"])
api_router.include_router(holidays.router, prefix="/hr", tags=["Human Resource"])