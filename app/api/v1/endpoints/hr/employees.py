from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_active_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.employee_service import EmployeeService
from app.schemas.hr.employee_schema import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.models.auth.user import User

router = APIRouter()

@router.post("/", response_model=EmployeeResponse)
async def create_employee(
    employee: EmployeeCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new employee"""
    service = EmployeeService(session)
    return await service.create_employee(employee, current_user.id)

@router.get("/", response_model=PaginatedResponse[EmployeeResponse])
async def get_employees(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    is_manager: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get all employees with filtering and pagination"""
    service = EmployeeService(session)
    return await service.get_employees(
        page_index=page_index,
        page_size=page_size,
        department_id=department_id,
        location_id=location_id,
        is_manager=is_manager,
        is_active=is_active,
        search=search
    )

@router.get("/managers", response_model=List[EmployeeResponse])
async def get_managers(
    location_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get all managers"""
    service = EmployeeService(session)
    return await service.get_managers(location_id)

@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get employee by ID"""
    service = EmployeeService(session)
    employee = await service.get_employee(employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    employee: EmployeeUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Update employee"""
    service = EmployeeService(session)
    return await service.update_employee(employee_id, employee, current_user.id)

@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
   session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Delete employee"""
    service = EmployeeService(session)
    result = await service.delete_employee(employee_id, current_user.id)
    return {"message": "Employee deleted successfully", "success": result}