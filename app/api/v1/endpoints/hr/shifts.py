from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.shift_service import ShiftService
from app.schemas.hr.shift_schema import (
    EmployeeShiftDetail, EmployeeShiftSummary, ShiftTypeCreate, ShiftTypeUpdate, ShiftTypeResponse,
    UserShiftCreate, UserShiftUpdate, UserShiftResponse
)
from app.models.auth.user import User

router = APIRouter()

# region Shift Type Endpoints

@router.post("/types", response_model=ShiftTypeResponse)
async def create_shift_type(
    shift_type: ShiftTypeCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new shift type"""
    service = ShiftService(session)
    return await service.create_shift_type(shift_type, current_user.id)

@router.get("/types", response_model=PaginatedResponse[ShiftTypeResponse])
async def get_shift_types(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all shift types with pagination"""
    service = ShiftService(session)
    return await service.get_shift_types(
        page_index=page_index,
        page_size=page_size,
        is_active=is_active
    )

@router.get("/types/{shift_type_id}", response_model=ShiftTypeResponse)
async def get_shift_type(
    shift_type_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific shift type by ID"""
    service = ShiftService(session)
    shift_type = await service.get_shift_type(shift_type_id)
    if not shift_type:
        raise HTTPException(status_code=404, detail="Shift type not found")
    return shift_type

@router.put("/types/{shift_type_id}", response_model=ShiftTypeResponse)
async def update_shift_type(
    shift_type_id: int,
    shift_type: ShiftTypeUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update shift type"""
    service = ShiftService(session)
    return await service.update_shift_type(shift_type_id, shift_type, current_user.id)

@router.get("/employee/{employee_id}/current", response_model=Optional[UserShiftResponse])
async def get_employee_current_shift(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee's current shift"""
    service = ShiftService(session)
    return await service.get_employee_current_shift(employee_id)

@router.get("/employee/{employee_id}/history", response_model=List[UserShiftResponse])
async def get_employee_shift_history(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee's shift history"""
    service = ShiftService(session)
    return await service.get_employee_shift_history(employee_id)

# endregion 

# region User Shift Endpoints

@router.post("/assign", response_model=UserShiftResponse)
async def assign_shift_to_employee(
    assignment: UserShiftCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Assign shift to employee"""
    service = ShiftService(session)
    return await service.assign_shift_to_employee(assignment, current_user.id)

@router.put("/assign/{user_shift_id}", response_model=UserShiftResponse)
async def update_user_shift(
    user_shift_id: int,
    shift_update: UserShiftUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update user shift assignment (e.g., set end_date or deactivate)"""
    service = ShiftService(session)
    return await service.update_user_shift(user_shift_id, shift_update, current_user.id)

@router.get("/employees/shifts", response_model=PaginatedResponse[EmployeeShiftSummary])
async def get_employee_shifts(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by employee name or employee ID"),
    start_date: Optional[date] = Query(None, description="Filter shifts by effective_date >= start_date"),
    end_date: Optional[date] = Query(None, description="Filter shifts by effective_date <= end_date"),
    is_active: Optional[bool] = Query(None, description="Filter by employee active status"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get employee shifts grouped by employee (one row per employee).
    """
    service = ShiftService(session)
    return await service.get_employee_shifts(
        page_index=page_index,
        page_size=page_size,
        search=search,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active
    )

@router.get("/employees/{employee_id}/shifts/detail", response_model=EmployeeShiftDetail)
async def get_employee_shift_details(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed shift information for a specific employee.
    """
    service = ShiftService(session)
    detail = await service.get_employee_shift_details(employee_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Employee shift details not found")
    return detail

# endregion