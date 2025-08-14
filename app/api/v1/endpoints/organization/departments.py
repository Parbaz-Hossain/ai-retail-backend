from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_active_user
from app.core.database import get_async_session
from app.services.organization.department_service import DepartmentService
from app.schemas.organization.department_schema import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.models.auth.user import User

router = APIRouter()

@router.post("/", response_model=DepartmentResponse)
async def create_department(
    department: DepartmentCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new department"""
    service = DepartmentService(session)
    return await service.create_department(department, current_user.id)

@router.get("/", response_model=List[DepartmentResponse])
async def get_departments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all departments with filtering"""
    service = DepartmentService(session)
    return await service.get_departments(skip, limit, search, is_active)

@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get department by ID"""
    service = DepartmentService(session)
    department = await service.get_department(department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return department

@router.put("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: int,
    department: DepartmentUpdate,
    session: AsyncSession = Depends(get_async_session)
):
    """Update department"""
    service = DepartmentService(session)
    return await service.update_department(department_id, department)

@router.delete("/{department_id}")
async def delete_department(
    department_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Delete department"""
    service = DepartmentService(session)
    result = await service.delete_department(department_id, current_user.id)
    return {"message": "Department deleted successfully", "success": result}